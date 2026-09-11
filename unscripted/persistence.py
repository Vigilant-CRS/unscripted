"""Persistence (spec v0.5 §8).

Event-sourced core: an append-only ledger plus materialized per-agent projections
(beliefs, memory, affect). Reason traces are debug-only (kept small). This module
implements the subset needed by the knowledge-spine + affect demo, with save/reload
that reproduces state (end-to-end case 20).
"""
from __future__ import annotations
import sqlite3
import json
import time
import hashlib
from .belief import Belief
from .memory import Memory
from .affect import AffectState

SCHEMA = """
CREATE TABLE IF NOT EXISTS event_ledger (
  entry INTEGER PRIMARY KEY AUTOINCREMENT, event_id INTEGER, world_time INTEGER,
  type TEXT, actor TEXT, location TEXT, payload TEXT, canonical INTEGER);
CREATE TABLE IF NOT EXISTS belief (
  owner TEXT, core_key TEXT, data TEXT, PRIMARY KEY (owner, core_key));
CREATE TABLE IF NOT EXISTS memory (
  memory_id TEXT PRIMARY KEY, owner TEXT, data TEXT);
CREATE TABLE IF NOT EXISTS affect (
  owner TEXT PRIMARY KEY, data TEXT);
CREATE TABLE IF NOT EXISTS reason_trace (
  event_id INTEGER, owner TEXT, entries TEXT);
CREATE TABLE IF NOT EXISTS provider_call (
  turn_id TEXT PRIMARY KEY, world_time INTEGER, provider TEXT, model_id TEXT,
  prompt_hash TEXT, raw_output TEXT, accepted_output TEXT, validation_result TEXT,
  data TEXT);
CREATE TABLE IF NOT EXISTS snapshot (
  snapshot_id TEXT PRIMARY KEY, label TEXT, created_at INTEGER, data TEXT);
CREATE TABLE IF NOT EXISTS meta (k TEXT PRIMARY KEY, v TEXT);
"""


class Store:
    def __init__(self, path=":memory:", debug_traces=True):
        # check_same_thread=False lets the connection be used from the HTTP
        # service's worker threads. Concurrent access is serialised by a lock in
        # the service layer (one world == sequential turns), so this is safe.
        self.conn = sqlite3.connect(path, check_same_thread=False)
        if path != ":memory:":
            # Write-ahead logging plus a relaxed fsync policy: this is a projection
            # store rebuilt from the event ledger, so trading a fsync per commit for
            # throughput is the right side of the durability/latency trade.
            self.conn.execute("PRAGMA journal_mode=WAL")
            self.conn.execute("PRAGMA synchronous=NORMAL")
        self.conn.executescript(SCHEMA)
        self._migrate_ledger()
        self.debug_traces = debug_traces
        self._pending = {table: [] for table in self._BATCHED}
        #: Reason traces are debug output. Unbounded, they outgrow the world state
        #: they explain; keep a rolling window instead. None disables trimming.
        self.reason_trace_limit = 20000
        self._traces_written = 0

    def _migrate_ledger(self) -> None:
        """Bring a store written before the ledger had its own row id forward.

        `CREATE TABLE IF NOT EXISTS` leaves an existing file on the old schema,
        where `event_id` is the primary key -- so an old save file would keep
        silently overwriting its own history after a restore. Copied rather than
        altered because SQLite cannot add a primary key in place, and in write
        order, which is the order the old table's rowid already preserves.
        """
        columns = [row[1] for row in
                   self.conn.execute("PRAGMA table_info(event_ledger)").fetchall()]
        if "entry" in columns or not columns:
            return
        self.conn.execute("ALTER TABLE event_ledger RENAME TO event_ledger_v1")
        self.conn.executescript(SCHEMA)
        self.conn.execute(
            "INSERT INTO event_ledger (event_id, world_time, type, actor, location,"
            " payload, canonical) SELECT event_id, world_time, type, actor,"
            " location, payload, canonical FROM event_ledger_v1 ORDER BY rowid")
        self.conn.execute("DROP TABLE event_ledger_v1")
        self.conn.commit()

    # ---- write batching ----
    # An event with N co-located observers produces ~3N row writes. Issued one at a
    # time these dominate the event path; batched into one executemany per table
    # they are a single round trip. Reads flush first, so a caller never observes a
    # stale projection.
    _BATCHED = {
        # APPEND, never replace. `event_id` used to be the primary key while
        # `restore` rewinds the counter that mints them, so loading an earlier
        # save and playing on OVERWROTE the abandoned branch's rows: event 1001
        # stopped being what happened and became whatever happened last under
        # that number. An append-only audit stream cannot have a key the
        # simulation reuses, so the row has its own.
        "event_ledger": ("INSERT INTO event_ledger "
                         "(event_id, world_time, type, actor, location, payload, "
                         "canonical) VALUES (?,?,?,?,?,?,?)"),
        "belief": "INSERT OR REPLACE INTO belief VALUES (?,?,?)",
        "memory": "INSERT OR REPLACE INTO memory VALUES (?,?,?)",
        "affect": "INSERT OR REPLACE INTO affect VALUES (?,?)",
        "reason_trace": "INSERT INTO reason_trace VALUES (?,?,?)",
    }

    def _queue(self, table: str, row: tuple):
        self._pending[table].append(row)

    def flush(self):
        """Write buffered rows without committing the transaction."""
        for table, rows in self._pending.items():
            if rows:
                self.conn.executemany(self._BATCHED[table], rows)
                rows.clear()

    def close(self):
        self.flush()
        self.conn.commit()
        self.conn.close()

    def commit(self):
        """Flush the current write batch. One commit per event/turn, not per row."""
        self.flush()
        self.conn.commit()

    def _read(self, sql, params=()):
        self.flush()
        return self.conn.execute(sql, params)

    # ---- ledger ----
    def append_event(self, ev):
        self._queue("event_ledger",
                    (ev.event_id, ev.world_time, ev.type, ev.actor, ev.location,
                     json.dumps(ev.payload, default=str), int(ev.canonical)))

    def event_count(self):
        return self._read("SELECT COUNT(*) FROM event_ledger").fetchone()[0]

    # ---- projections (write-through) ----
    # Writes do NOT commit individually. The runtime knows the boundary of a
    # logical change (one event, one turn) and commits there. save_agent() used to
    # re-serialise every belief and every memory of every observer on every event
    # and commit per agent, which made persistence ~94% of per-event cost.
    def save_belief(self, owner, belief: Belief):
        self._queue("belief",
                    (owner, belief.proposition.core_key(), json.dumps(belief.as_dict())))

    def save_memory(self, owner, mem: Memory):
        self._queue("memory", (mem.memory_id, owner, json.dumps(mem.as_dict())))

    def delete_memories(self, owner, memory_ids):
        """Forgotten memories must leave the projection too, or the store keeps
        growing with episodes the agent no longer has."""
        rows = [(mid, owner) for mid in memory_ids]
        if not rows:
            return
        self.flush()   # a queued insert for a dropped memory must not outlive it
        self.conn.executemany("DELETE FROM memory WHERE memory_id=? AND owner=?", rows)

    def save_affect(self, owner, affect: AffectState):
        self._queue("affect", (owner, json.dumps(affect.as_dict())))

    def save_agent(self, agent, *, commit: bool = True):
        """Full rewrite of an agent's projections. Use the targeted savers on the
        hot path; this is for seeding and for callers that changed an unknown set."""
        for b in agent.beliefs.values():
            self.save_belief(agent.id, b)
        for m in agent.memory:
            self.save_memory(agent.id, m)
        self.save_affect(agent.id, agent.affect)
        if commit:
            self.conn.commit()

    def save_reason_trace(self, event_id, owner, entries):
        if not self.debug_traces:
            return
        self._queue("reason_trace", (event_id, owner, json.dumps(entries, default=str)))
        self._traces_written += 1
        if self.reason_trace_limit and self._traces_written >= 512:
            self._trim_reason_traces()

    def _trim_reason_traces(self):
        self._traces_written = 0
        self.flush()
        self.conn.execute(
            "DELETE FROM reason_trace WHERE rowid NOT IN "
            "(SELECT rowid FROM reason_trace ORDER BY rowid DESC LIMIT ?)",
            (self.reason_trace_limit,))

    def reason_trace_count(self):
        return self._read("SELECT COUNT(*) FROM reason_trace").fetchone()[0]

    def save_provider_call(self, *, turn_id, world_time, provider, model_id,
                           prompt_hash, raw_output, accepted_output,
                           validation_result, data=None):
        self.conn.execute("INSERT OR REPLACE INTO provider_call VALUES (?,?,?,?,?,?,?,?,?)",
                          (turn_id, world_time, provider, model_id, prompt_hash,
                           raw_output, accepted_output, validation_result,
                           json.dumps(data or {}, default=str)))
        self.conn.commit()

    def provider_call_count(self):
        return self._read("SELECT COUNT(*) FROM provider_call").fetchone()[0]

    # ---- snapshots ----
    # The Store persists an opaque, already-serialised snapshot blob. Deciding
    # *what* belongs in a snapshot is runtime semantics and lives in unscripted.snapshot,
    # so the round-trip is testable without a database and the storage layer does
    # not need to know about agents, factions or conversations.
    def save_snapshot(self, data: dict, label=None) -> str:
        self.flush()
        self.conn.commit()
        raw = json.dumps(data, sort_keys=True, default=str)
        ts = int(time.time())
        snapshot_id = hashlib.sha256(f"{label or ''}:{ts}:{raw}".encode("utf-8")).hexdigest()[:16]
        self.conn.execute("INSERT OR REPLACE INTO snapshot VALUES (?,?,?,?)",
                          (snapshot_id, label, ts, raw))
        self.conn.commit()
        return snapshot_id

    def load_snapshot(self, snapshot_id):
        row = self._read("SELECT data FROM snapshot WHERE snapshot_id=?",
                         (snapshot_id,)).fetchone()
        if not row:
            raise KeyError(f"Unknown snapshot id: {snapshot_id}")
        return json.loads(row[0])

    def list_snapshots(self):
        return [{"snapshot_id": sid, "label": label, "created_at": created}
                for sid, label, created in self._read(
                    "SELECT snapshot_id, label, created_at FROM snapshot ORDER BY created_at")]

    def diffusion_events(self, limit: int = 50):
        """Recent retellings, newest last: who told whom what, and where.

        The audit trail behind "how did this NPC know that?". Reading it from the
        ledger rather than keeping a second in-memory log means the answer survives
        a restart and cannot drift from what actually happened.
        """
        rows = self._read(
            "SELECT event_id, world_time, actor, location, payload FROM event_ledger "
            "WHERE type='claim' AND payload LIKE '%\"diffusion\"%' "
            "ORDER BY event_id DESC LIMIT ?", (limit,)).fetchall()
        out = []
        for event_id, world_time, actor, location, payload in reversed(rows):
            try:
                data = json.loads(payload)
            except json.JSONDecodeError:
                continue
            spread = data.get("diffusion") or {}
            out.append({
                "event_id": event_id, "world_time": world_time,
                "from": actor, "to": spread.get("listener"), "place": location,
                "hops": spread.get("hops"), "distorted": bool(spread.get("distorted")),
                "distortion_kind": spread.get("distortion_kind"),
                "distortion_detail": spread.get("distortion_detail") or {},
                "origin": data.get("origin_event"),
                # How it was said. A debug HUD that cannot tell a conversation
                # from a phone call cannot explain why one of them lost a detail.
                "medium": data.get("medium", "in_person"),
                "proposition": (data.get("proposition") or {}).get("predicate"),
            })
        return out

    def ledger_position(self):
        """The ledger's own high-water mark: the last row WRITTEN.

        Not an event id. Event ids are minted by the simulation and `restore`
        rewinds the counter that mints them, so they are not monotonic across a
        reload and cannot mark a point in an audit stream.
        """
        row = self._read("SELECT MAX(entry) FROM event_ledger").fetchone()
        return int(row[0]) if row and row[0] is not None else 0

    def ledger_as_of(self, entry_watermark):
        """The ledger as it stood when this watermark was taken.

        THE WATERMARK IS A ROW ID, and this is the half of the branch problem
        that `entry` alone did not fix. Both branches survive now -- that was the
        overwrite -- but the query that reads "the history as of snapshot A" was
        still filtering on `event_id <= watermark`, and after a reload the new
        branch mints the same ids. So A's own history grew a future it never had:
        the same call returned A, and later A and B.
        """
        cur = self._read(
            "SELECT * FROM event_ledger WHERE entry <= ? ORDER BY entry",
            (entry_watermark,))
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]

    # ---- load (reload reproduces state) ----
    def load_beliefs(self, owner):
        return {ck: Belief.from_dict(json.loads(data))
                for ck, data in self._read(
                    "SELECT core_key, data FROM belief WHERE owner=?", (owner,))}

    def load_memories(self, owner):
        return [Memory.from_dict(json.loads(data), owner=owner)
                for (data,) in self._read(
                    "SELECT data FROM memory WHERE owner=?", (owner,))]

    def load_affect(self, owner):
        row = self._read("SELECT data FROM affect WHERE owner=?", (owner,)).fetchone()
        return AffectState.from_dict(json.loads(row[0])) if row else None
