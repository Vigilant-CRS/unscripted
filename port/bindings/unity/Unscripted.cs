// Unity binding for the Unscripted runtime.
//
// Drop this file and the native library into `Assets/Plugins/Unscripted/`.
// Nothing here is Unity-specific beyond the library name, which is why it is
// also what the test harness compiles: the marshalling is the part that can be
// wrong, and it can be proved without an editor.
//
// THE TWO MISTAKES THIS FILE EXISTS TO AVOID, both of which crash rather than
// misbehave, and neither of which shows up until runtime:
//
//   1. A `string` RETURN value. `[return: MarshalAs(UnmanagedType.LPUTF8Str)]`
//      makes the runtime free the pointer with the COM allocator when it comes
//      back. The strings this library returns belong to the library. Freeing
//      them corrupts its heap. So every returned string is an `IntPtr` and is
//      copied with `Marshal.PtrToStringUTF8`.
//   2. Holding a returned pointer across another call. The buffer is reused, so
//      the second call rewrites what the first returned. Every wrapper below
//      copies immediately, which is also why the public surface is `string`.
//
// IL2CPP: the library is linked statically on platforms that forbid dynamic
// loading, and `__Internal` is the DllImport name there. That is what the
// `USC_STATIC` switch below is for -- a console build sets it, a
// desktop build does not.
using System;
using System.Runtime.InteropServices;

namespace Unscripted
{
    public enum UscStatus
    {
        Ok = 0,
        BadArgument = 1,
        BadPack = 2,
        BadState = 3,
        BadSave = 4,
        Refused = 5,
    }

    /// <summary>A call the runtime refused, with the reason it gave.</summary>
    public sealed class UnscriptedException : Exception
    {
        public UscStatus Status { get; }

        public UnscriptedException(UscStatus status, string message)
            : base(message) { Status = status; }
    }

    internal static class Native
    {
#if USC_STATIC
        private const string Library = "__Internal";
#else
        private const string Library = "usc";
#endif

        [DllImport(Library, CallingConvention = CallingConvention.Cdecl)]
        internal static extern int usc_abi_version();

        [DllImport(Library, CallingConvention = CallingConvention.Cdecl)]
        internal static extern IntPtr usc_runtime_version();

        [DllImport(Library, CallingConvention = CallingConvention.Cdecl)]
        internal static extern IntPtr usc_last_error(IntPtr runtime);

        [DllImport(Library, CallingConvention = CallingConvention.Cdecl)]
        internal static extern UscStatus usc_open(
            [MarshalAs(UnmanagedType.LPUTF8Str)] string packPath,
            IntPtr[] characterFiles,
            [MarshalAs(UnmanagedType.LPUTF8Str)] string configJson,
            out IntPtr runtime);

        [DllImport(Library, CallingConvention = CallingConvention.Cdecl)]
        internal static extern void usc_close(IntPtr runtime);

        [DllImport(Library, CallingConvention = CallingConvention.Cdecl)]
        internal static extern long usc_world_time(IntPtr runtime);

        [DllImport(Library, CallingConvention = CallingConvention.Cdecl)]
        internal static extern UscStatus usc_advance_time(IntPtr runtime, long minutes);

        [DllImport(Library, CallingConvention = CallingConvention.Cdecl)]
        internal static extern UscStatus usc_submit_player_text(
            IntPtr runtime, [MarshalAs(UnmanagedType.LPUTF8Str)] string text,
            out IntPtr json);

        [DllImport(Library, CallingConvention = CallingConvention.Cdecl)]
        internal static extern UscStatus usc_respond(
            IntPtr runtime, [MarshalAs(UnmanagedType.LPUTF8Str)] string agentId,
            [MarshalAs(UnmanagedType.LPUTF8Str)] string topic, out IntPtr json);

        [DllImport(Library, CallingConvention = CallingConvention.Cdecl)]
        internal static extern UscStatus usc_agent_state(
            IntPtr runtime, [MarshalAs(UnmanagedType.LPUTF8Str)] string agentId,
            out IntPtr json);

        [DllImport(Library, CallingConvention = CallingConvention.Cdecl)]
        internal static extern UscStatus usc_knowledge_state(
            IntPtr runtime, long limit, out IntPtr json);

        [DllImport(Library, CallingConvention = CallingConvention.Cdecl)]
        internal static extern UscStatus usc_world_state(IntPtr runtime, out IntPtr json);

        [DllImport(Library, CallingConvention = CallingConvention.Cdecl)]
        internal static extern UscStatus usc_scene_state(IntPtr runtime, out IntPtr json);

        [DllImport(Library, CallingConvention = CallingConvention.Cdecl)]
        internal static extern UscStatus usc_face_packet(
            IntPtr runtime, [MarshalAs(UnmanagedType.LPUTF8Str)] string agentId,
            [MarshalAs(UnmanagedType.LPUTF8Str)] string gazeTarget, out IntPtr json);

        [DllImport(Library, CallingConvention = CallingConvention.Cdecl)]
        internal static extern UscStatus usc_export_state(IntPtr runtime, out IntPtr json);

        [DllImport(Library, CallingConvention = CallingConvention.Cdecl)]
        internal static extern UscStatus usc_inspect_state(
            IntPtr runtime, [MarshalAs(UnmanagedType.LPUTF8Str)] string blobJson,
            out IntPtr json);

        [DllImport(Library, CallingConvention = CallingConvention.Cdecl)]
        internal static extern UscStatus usc_import_state(
            IntPtr runtime, [MarshalAs(UnmanagedType.LPUTF8Str)] string blobJson,
            out IntPtr json);

        [DllImport(Library, CallingConvention = CallingConvention.Cdecl)]
        internal static extern UscStatus usc_pending_actions(IntPtr runtime,
                                                             out IntPtr json);

        [DllImport(Library, CallingConvention = CallingConvention.Cdecl)]
        internal static extern UscStatus usc_resolve_action(
            IntPtr runtime, [MarshalAs(UnmanagedType.LPUTF8Str)] string intentId,
            [MarshalAs(UnmanagedType.LPUTF8Str)] string status,
            [MarshalAs(UnmanagedType.LPUTF8Str)] string detail, out IntPtr json);

        [DllImport(Library, CallingConvention = CallingConvention.Cdecl)]
        internal static extern UscStatus usc_discredit(
            IntPtr runtime, [MarshalAs(UnmanagedType.LPUTF8Str)] string sourceId,
            double factor, [MarshalAs(UnmanagedType.LPUTF8Str)] string reason,
            out IntPtr json);

        [DllImport(Library, CallingConvention = CallingConvention.Cdecl)]
        internal static extern UscStatus usc_inspect_agent(
            IntPtr runtime, [MarshalAs(UnmanagedType.LPUTF8Str)] string agentId,
            out IntPtr text);
    }

    /// <summary>One world, one player, one simulation.</summary>
    public sealed class World : IDisposable
    {
        /// <summary>The ABI this binding was written against.</summary>
        public const int ExpectedAbiVersion = 1;

        private IntPtr _handle;

        public static int AbiVersion => Native.usc_abi_version();
        public static string RuntimeVersion => Utf8(Native.usc_runtime_version());

        /// <summary>
        /// Open a world pack.
        /// </summary>
        /// <param name="characterFiles">
        /// The basenames inside the pack's <c>characters/</c> directory.
        /// REQUIRED, because listing a directory is the one thing a console does
        /// differently -- on a packed build the files are in an archive and the
        /// game is the only thing that knows what is in it.
        /// </param>
        public World(string packPath, string[] characterFiles, string configJson = null)
        {
            if (packPath == null) throw new ArgumentNullException(nameof(packPath));
            if (characterFiles == null)
                throw new ArgumentNullException(nameof(characterFiles));
            if (AbiVersion != ExpectedAbiVersion)
                throw new UnscriptedException(
                    UscStatus.Refused,
                    $"the native library speaks ABI {AbiVersion} and this binding " +
                    $"speaks {ExpectedAbiVersion}");

            // A NULL-terminated array of UTF-8 pointers, built by hand: the
            // default marshaller for `string[]` does not add the terminator the
            // C side reads, and there is no attribute that asks it to.
            var pointers = new IntPtr[characterFiles.Length + 1];
            try
            {
                for (int i = 0; i < characterFiles.Length; i++)
                    pointers[i] = Marshal.StringToCoTaskMemUTF8(characterFiles[i]);
                pointers[characterFiles.Length] = IntPtr.Zero;

                var status = Native.usc_open(packPath, pointers, configJson, out _handle);
                if (status != UscStatus.Ok)
                    throw new UnscriptedException(status, Utf8(Native.usc_last_error(IntPtr.Zero)));
            }
            finally
            {
                foreach (var pointer in pointers)
                    if (pointer != IntPtr.Zero) Marshal.FreeCoTaskMem(pointer);
            }
        }

        public void Dispose()
        {
            if (_handle == IntPtr.Zero) return;
            Native.usc_close(_handle);
            _handle = IntPtr.Zero;
        }

        public long WorldTime => Native.usc_world_time(Handle);

        public void AdvanceTime(long minutes) =>
            Check(Native.usc_advance_time(Handle, minutes));

        /// <summary>One turn of player text. Returns the answer as JSON.</summary>
        public string SubmitPlayerText(string text) =>
            Call((out IntPtr json) => Native.usc_submit_player_text(Handle, text, out json));

        public string Respond(string agentId, string topic = null) =>
            Call((out IntPtr json) => Native.usc_respond(Handle, agentId, topic, out json));

        public string AgentState(string agentId) =>
            Call((out IntPtr json) => Native.usc_agent_state(Handle, agentId, out json));

        public string KnowledgeState(long limit = 40) =>
            Call((out IntPtr json) => Native.usc_knowledge_state(Handle, limit, out json));

        public string WorldState() =>
            Call((out IntPtr json) => Native.usc_world_state(Handle, out json));

        public string SceneState() =>
            Call((out IntPtr json) => Native.usc_scene_state(Handle, out json));

        /// <summary>ARKit blendshapes, gaze, prosody and posture for one character.</summary>
        public string FacePacket(string agentId, string gazeTarget = null) =>
            Call((out IntPtr json) => Native.usc_face_packet(Handle, agentId, gazeTarget, out json));

        /// <summary>The whole mutable world, for the game's own save file.</summary>
        public string ExportState() =>
            Call((out IntPtr json) => Native.usc_export_state(Handle, out json));

        /// <summary>What loading this blob would do, without loading it.</summary>
        public string InspectState(string blobJson) =>
            Call((out IntPtr json) => Native.usc_inspect_state(Handle, blobJson, out json));

        public string ImportState(string blobJson) =>
            Call((out IntPtr json) => Native.usc_import_state(Handle, blobJson, out json));

        /// <summary>What the engine still owes an answer for.</summary>
        public string PendingActions() =>
            Call((out IntPtr json) => Native.usc_pending_actions(Handle, out json));

        public string ResolveAction(string intentId, string status, string detail = null) =>
            Call((out IntPtr json) =>
                Native.usc_resolve_action(Handle, intentId, status, detail, out json));

        public string Discredit(string sourceId, double factor = 0.25,
                                string reason = "exposed") =>
            Call((out IntPtr json) =>
                Native.usc_discredit(Handle, sourceId, factor, reason, out json));

        public string InspectAgent(string agentId) =>
            Call((out IntPtr text) => Native.usc_inspect_agent(Handle, agentId, out text));

        public string LastError => Utf8(Native.usc_last_error(Handle));

        private delegate UscStatus OutJson(out IntPtr value);

        private IntPtr Handle =>
            _handle != IntPtr.Zero ? _handle
                                   : throw new ObjectDisposedException(nameof(World));

        private string Call(OutJson body)
        {
            IntPtr value;
            var status = body(out value);
            if (status != UscStatus.Ok)
                throw new UnscriptedException(status, LastError);
            // COPIED HERE, not held: the buffer belongs to the runtime and the
            // next call rewrites it.
            return Utf8(value);
        }

        private void Check(UscStatus status)
        {
            if (status != UscStatus.Ok)
                throw new UnscriptedException(status, LastError);
        }

        private static string Utf8(IntPtr pointer) =>
            pointer == IntPtr.Zero ? string.Empty : Marshal.PtrToStringUTF8(pointer);
    }
}
