using System;
using System.Diagnostics;
using System.IO;
using UnityEngine;

namespace Vigilant.Unscripted
{
    /// <summary>
    /// Starts the runtime as a child process and tells you when it is reachable.
    /// </summary>
    /// <remarks>
    /// A game cannot hard-code a port: two copies of the same game, a dev server
    /// already on 8765, or a player with something else there are all ordinary
    /// and all fatal to a fixed number. So the service is asked for
    /// <c>--port 0</c>, the OS chooses, and it writes where it landed to a file
    /// this polls.
    ///
    /// It also handles the part everybody forgets. <c>--parent-pid</c> makes the
    /// service exit when this process does, INCLUDING when the game crashes.
    /// Games crash, and a service left holding a port and a save is an afternoon
    /// of somebody's life.
    ///
    /// <code>
    /// var host = gameObject.AddComponent&lt;UnscriptedHost&gt;();
    /// host.ReadyAt += (url, token) =&gt; client.ConnectTo(url, token);
    /// host.StartRuntime("Assets/StreamingAssets/my-town", new[]{"pursuit","promises"});
    /// </code>
    /// </remarks>
    public class UnscriptedHost : MonoBehaviour
    {
        /// <summary>The service is listening. Subscribe BEFORE calling StartRuntime.</summary>
        public event Action<string, string> ReadyAt;
        /// <summary>It never came up, with a reason worth showing a developer.</summary>
        public event Action<string> Failed;

        [Tooltip("Interpreter, or the bundled runtime. `unscripted bundle` writes a single file that any Python 3.10+ runs.")]
        public string python = "python3";
        [Tooltip("Empty means `-m unscripted`. Point this at unscripted.pyz to ship without an install.")]
        public string bundlePath = "";
        [Tooltip("Seconds to wait for the service before giving up.")]
        public float startupTimeout = 30f;

        Process _process;
        string _announcePath;
        float _elapsed;
        bool _waiting;

        public void StartRuntime(string worldPack, string[] layers = null)
        {
            if (_waiting || _process != null)
            {
                UnityEngine.Debug.LogWarning("UnscriptedHost.StartRuntime called twice; ignoring the second.");
                return;
            }

            // persistentDataPath, not the project folder: in a built game the
            // project folder is inside the package and is not writable.
            _announcePath = Path.Combine(Application.persistentDataPath,
                $"unscripted_{Process.GetCurrentProcess().Id}.json");
            if (File.Exists(_announcePath)) File.Delete(_announcePath);

            var token = MakeToken();
            var arguments = string.IsNullOrEmpty(bundlePath) ? "-m unscripted" : Quote(bundlePath);
            arguments += " serve"
                + " --world-pack " + Quote(Path.GetFullPath(worldPack))
                + " --port 0"
                + " --announce " + Quote(_announcePath)
                + " --auth-token " + token
                + " --parent-pid " + Process.GetCurrentProcess().Id;
            if (layers != null && layers.Length > 0)
                arguments += " --layers " + string.Join(",", layers);

            try
            {
                _process = new Process
                {
                    StartInfo = new ProcessStartInfo(python, arguments)
                    {
                        UseShellExecute = false,
                        CreateNoWindow = true,
                        RedirectStandardOutput = true,
                        RedirectStandardError = true,
                    }
                };
                _process.Start();
            }
            catch (Exception exception)
            {
                Failed?.Invoke($"Could not launch '{python}'. Is Python installed and on PATH? ({exception.Message})");
                _process = null;
                return;
            }

            _waiting = true;
            _elapsed = 0f;
        }

        void Update()
        {
            if (!_waiting) return;
            _elapsed += Time.unscaledDeltaTime;

            // Poll the FILE rather than the port. The service writes it only once
            // it is actually listening, so seeing it means the next request is
            // answered. Polling a port instead connects during the bind and then
            // fails on the first real call, which is a far more confusing failure.
            if (File.Exists(_announcePath))
            {
                string text;
                try { text = File.ReadAllText(_announcePath); }
                catch (IOException) { return; }   // written but not yet closed
                Announcement announcement;
                try { announcement = JsonUtility.FromJson<Announcement>(text); }
                catch (Exception) { return; }
                if (announcement == null || string.IsNullOrEmpty(announcement.url)) return;
                _waiting = false;
                ReadyAt?.Invoke(announcement.url, announcement.token);
                return;
            }

            if (_elapsed > startupTimeout)
            {
                _waiting = false;
                var said = "";
                try { if (_process != null && _process.HasExited) said = _process.StandardError.ReadToEnd(); }
                catch (Exception) { }
                Failed?.Invoke(
                    $"The runtime did not start within {startupTimeout:0} s. Run this by hand to see why:\n"
                    + $"  {python} -m unscripted serve --world-pack <your pack>\n{said}");
            }
        }

        public void StopRuntime()
        {
            _waiting = false;
            if (_process == null) return;
            try
            {
                // The service handles SIGTERM and shuts down cleanly, removing
                // its own announce file. --parent-pid is the backstop for the
                // case where we never get here at all.
                if (!_process.HasExited) _process.Kill();
                _process.WaitForExit(5000);
            }
            catch (Exception) { }
            _process = null;
        }

        void OnDestroy() { StopRuntime(); }
        void OnApplicationQuit() { StopRuntime(); }

        static string Quote(string value) { return "\"" + value + "\""; }

        static string MakeToken()
        {
            // Not a secret worth defending against a determined attacker on the
            // same machine. It stops OTHER local software from talking to a
            // service started for this game, which is the actual risk on a
            // player's PC.
            var bytes = new byte[24];
            var random = new System.Random();
            random.NextBytes(bytes);
            return Convert.ToBase64String(bytes).Replace("/", "_").Replace("+", "-").Replace("=", "");
        }

        // JsonUtility fills these by reflection, which the compiler cannot see,
        // so it warns that they are never assigned. The warning is correct about
        // the code and wrong about the program; suppressed narrowly, here, with
        // the reason, rather than turned off for the assembly.
#pragma warning disable 0649
        [Serializable]
        class Announcement
        {
            public string url;
            public string token;
            public int port;
            public int pid;
        }
#pragma warning restore 0649
    }
}
