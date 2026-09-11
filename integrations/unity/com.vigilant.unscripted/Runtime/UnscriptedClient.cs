using System;
using System.Collections;
using System.Collections.Generic;
using System.Text;
using UnityEngine;
using UnityEngine.Networking;

namespace Vigilant.Unscripted
{
    /// <summary>
    /// Every endpoint a shipping game needs, in one component.
    /// </summary>
    /// <remarks>
    /// Requests are queued and run one at a time, in order, so a turn cannot
    /// overtake the event that caused it. Nothing here blocks a frame.
    ///
    /// Responses arrive as raw JSON strings rather than parsed objects, and that
    /// is deliberate: Unity's JsonUtility cannot represent the runtime's nested,
    /// heterogeneous payloads, and shipping a bespoke parser here would mean two
    /// definitions of the contract that could drift apart. Use whatever JSON
    /// library your project already has — the shapes are in
    /// integrations/unreal/UnscriptedBridge/contract.v2.json.
    /// </remarks>
    public class UnscriptedClient : MonoBehaviour
    {
        /// <summary>A character answered: the JSON of /v2/avatar/turn.</summary>
        public event Action<string> Spoke;
        /// <summary>The world advanced: the JSON of /advance.</summary>
        public event Action<string> Advanced;
        /// <summary>A gameplay event was accepted, with who perceived it.</summary>
        public event Action<string> EventAccepted;
        /// <summary>The runtime wants your engine to carry something out.</summary>
        public event Action<string> ActionsPending;
        /// <summary>The save blob, for your own save file.</summary>
        public event Action<string> StateExported;
        /// <summary>A load was inspected or performed.</summary>
        public event Action<string> StateReport;
        /// <summary>Open and recently settled promises.</summary>
        public event Action<string> Promises;
        /// <summary>Something went wrong, with a message worth showing a developer.</summary>
        public event Action<string> Failed;

        public string BaseUrl { get; private set; } = "";
        string _token = "";
        readonly Queue<Job> _queue = new Queue<Job>();
        bool _busy;

        public void ConnectTo(string url, string authToken)
        {
            BaseUrl = url.TrimEnd('/');
            _token = authToken;
            // Ask what this build can do before assuming any of it. "Off" and
            // "not in this build" look identical from outside, and finding out
            // the hard way means writing a HUD against a mechanic that is not
            // running.
            Get("/capabilities", body =>
            {
                if (!body.Contains("\"2.0.0\""))
                    Failed?.Invoke("This runtime does not speak contract 2.0.0.");
            });
        }

        // ------------------------------------------------------------ dialogue --

        public void Say(string text) =>
            Post("/v2/avatar/turn", Body(("text", text)), body => Spoke?.Invoke(body));

        // ------------------------------------------------------------ gameplay --

        /// <summary>
        /// THE ONE YOU WILL USE MOST. A door forced, a body found, a payment
        /// made: send what characters could plausibly perceive or hear about,
        /// and let the runtime decide who actually did.
        /// </summary>
        public void SendEvent(string type, string payloadJson, string location = "", string actor = "")
        {
            var json = new StringBuilder("{\"type\":").Append(Quote(type))
                .Append(",\"payload\":").Append(string.IsNullOrEmpty(payloadJson) ? "{}" : payloadJson);
            if (!string.IsNullOrEmpty(location)) json.Append(",\"location\":").Append(Quote(location));
            if (!string.IsNullOrEmpty(actor)) json.Append(",\"actor\":").Append(Quote(actor));
            json.Append('}');
            Post("/event", json.ToString(), body => EventAccepted?.Invoke(body));
        }

        public void Advance(int minutes) =>
            Post("/advance", "{\"minutes\":" + minutes + "}", body => Advanced?.Invoke(body));

        public void Discredit(string sourceId, float factor = 0.35f, string reason = "caught out") =>
            Post("/v2/discredit",
                "{\"source\":" + Quote(sourceId) + ",\"factor\":" + factor.ToString("0.###",
                    System.Globalization.CultureInfo.InvariantCulture)
                    + ",\"reason\":" + Quote(reason) + "}",
                _ => { });

        // ------------------------------------------------------ what it asks --

        public void FetchPendingActions() =>
            Get("/v2/actions/pending", body => ActionsPending?.Invoke(body));

        /// <summary>
        /// SUCCEEDED, FAILED, INTERRUPTED or UNREACHABLE. Answer every intent:
        /// a bridge that is enabled and never answered is a cast that never
        /// arrives anywhere.
        /// </summary>
        public void ReportAction(string intentId, string status, string detail = "") =>
            Post($"/v2/actions/{intentId}/result", Body(("status", status), ("detail", detail)), _ => { });

        /// <summary>
        /// Your game knows whether the player handed over the money. Say so,
        /// rather than hoping an NPC was paying attention.
        /// </summary>
        public void SettlePromise(string promiseId, bool kept, string note = "") =>
            Post($"/v2/promises/{promiseId}/settle",
                "{\"kept\":" + (kept ? "true" : "false") + ",\"note\":" + Quote(note) + "}",
                _ => { });

        public void FetchPromises() => Get("/v2/promises", body => Promises?.Invoke(body));

        // -------------------------------------------------------- save / load --

        /// <summary>Put the result into YOUR save file, next to everything else.</summary>
        public void ExportState() => Get("/v2/state/export", body => StateExported?.Invoke(body));

        /// <summary>
        /// What loading it WOULD do. Call this on a load screen before offering
        /// "continue": `usable` is a field, not an exception.
        /// </summary>
        public void InspectState(string blobJson) =>
            Post("/v2/state/inspect", "{\"state\":" + blobJson + "}", body => StateReport?.Invoke(body));

        public void ImportState(string blobJson) =>
            Post("/v2/state/import", "{\"state\":" + blobJson + "}", body => StateReport?.Invoke(body));

        // --------------------------------------------------------- transport --

        void Get(string path, Action<string> onDone) => Enqueue(new Job(path, null, onDone));
        void Post(string path, string body, Action<string> onDone) => Enqueue(new Job(path, body ?? "{}", onDone));

        void Enqueue(Job job)
        {
            if (string.IsNullOrEmpty(BaseUrl))
            {
                Failed?.Invoke("Not connected yet. Wait for UnscriptedHost.ReadyAt.");
                return;
            }
            _queue.Enqueue(job);
            if (!_busy) StartCoroutine(Pump());
        }

        IEnumerator Pump()
        {
            _busy = true;
            while (_queue.Count > 0)
            {
                var job = _queue.Dequeue();
                using (var request = Build(job))
                {
                    yield return request.SendWebRequest();
                    var text = request.downloadHandler != null ? request.downloadHandler.text : "";
                    if (request.result != UnityWebRequest.Result.Success)
                    {
                        // The service always answers with {error, code}, so a
                        // failure says what it was rather than only how it failed.
                        Failed?.Invoke($"{job.Path} {(long)request.responseCode}: "
                                       + (string.IsNullOrEmpty(text) ? request.error : text));
                    }
                    else
                    {
                        job.OnDone?.Invoke(text);
                    }
                }
            }
            _busy = false;
        }

        UnityWebRequest Build(Job job)
        {
            UnityWebRequest request;
            if (job.Body == null)
            {
                request = UnityWebRequest.Get(BaseUrl + job.Path);
            }
            else
            {
                request = new UnityWebRequest(BaseUrl + job.Path, "POST")
                {
                    uploadHandler = new UploadHandlerRaw(Encoding.UTF8.GetBytes(job.Body)),
                    downloadHandler = new DownloadHandlerBuffer(),
                };
                request.SetRequestHeader("Content-Type", "application/json");
            }
            request.SetRequestHeader("Authorization", "Bearer " + _token);
            return request;
        }

        static string Body(params (string Key, string Value)[] fields)
        {
            var json = new StringBuilder("{");
            for (var i = 0; i < fields.Length; i++)
            {
                if (i > 0) json.Append(',');
                json.Append(Quote(fields[i].Key)).Append(':').Append(Quote(fields[i].Value ?? ""));
            }
            return json.Append('}').ToString();
        }

        static string Quote(string value)
        {
            var json = new StringBuilder("\"");
            foreach (var character in value ?? "")
            {
                switch (character)
                {
                    case '"': json.Append("\\\""); break;
                    case '\\': json.Append("\\\\"); break;
                    case '\n': json.Append("\\n"); break;
                    case '\r': json.Append("\\r"); break;
                    case '\t': json.Append("\\t"); break;
                    default:
                        if (character < 0x20) json.Append("\\u").Append(((int)character).ToString("x4"));
                        else json.Append(character);
                        break;
                }
            }
            return json.Append('"').ToString();
        }

        class Job
        {
            public readonly string Path;
            public readonly string Body;
            public readonly Action<string> OnDone;
            public Job(string path, string body, Action<string> onDone)
            { Path = path; Body = body; OnDone = onDone; }
        }
    }
}
