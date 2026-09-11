using System.Collections;
using NUnit.Framework;
using UnityEngine;
using UnityEngine.TestTools;

namespace Vigilant.Unscripted.Tests
{
    /// <summary>
    /// Does the package BEHAVE, as opposed to merely compile?
    /// </summary>
    /// <remarks>
    /// The Unreal plugin compiled cleanly for months and still did two things
    /// wrong that no compiler could see: it dropped the `honesty` field the
    /// contract promises, and a version pin made the engine refuse to load it at
    /// all. Both were found by writing tests like these. Unity gets the same
    /// treatment.
    ///
    /// The service's address arrives in UNSCRIPTED_URL and UNSCRIPTED_TOKEN.
    /// tools/unity_smoke.py starts a real service on a free port and puts them
    /// there. Without them the tests say so and are inconclusive, because a test
    /// that passes when it could not reach anything is worse than no test.
    /// </remarks>
    public class UnscriptedClientTests
    {
        static string Url => System.Environment.GetEnvironmentVariable("UNSCRIPTED_URL");
        static string Token => System.Environment.GetEnvironmentVariable("UNSCRIPTED_TOKEN");

        GameObject _host;
        UnscriptedClient _client;

        [SetUp]
        public void SetUp()
        {
            if (string.IsNullOrEmpty(Url))
            {
                Assert.Ignore("UNSCRIPTED_URL is not set. Run these through "
                              + "tools/unity_smoke.py, which starts a service "
                              + "and points them at it.");
            }
            _host = new GameObject("UnscriptedTestHost");
            _client = _host.AddComponent<UnscriptedClient>();
            _client.ConnectTo(Url, Token);
        }

        [TearDown]
        public void TearDown()
        {
            if (_host != null) { Object.DestroyImmediate(_host); }
        }

        /// One request, waited on by yielding frames -- coroutines need them.
        static IEnumerator Until(System.Func<bool> done, float seconds = 20f)
        {
            var deadline = Time.realtimeSinceStartup + seconds;
            while (!done() && Time.realtimeSinceStartup < deadline)
            {
                yield return null;
            }
        }

        [UnityTest]
        public IEnumerator ATurnComesBackAndCarriesHonesty()
        {
            string body = null, failure = null;
            _client.Spoke += json => body = json;
            _client.Failed += reason => failure = reason;

            _client.Say("ask Yara about the shooting");
            yield return Until(() => body != null || failure != null);

            Assert.IsNull(failure, "the turn failed: " + failure);
            Assert.IsNotNull(body, "no answer within the timeout");

            // THE FIELD THE UNREAL PLUGIN DROPPED. Unity passes raw JSON through,
            // so nothing can be lost on this side -- which also means nothing
            // checks it. This is that check.
            StringAssert.Contains("\"honesty\"", body,
                "the avatar packet carries no honesty; a game cannot tell "
                + "whether the character lied, which is the point of the runtime");
            StringAssert.Contains("\"asserted\"", body,
                "the avatar packet carries no asserted list");
            StringAssert.Contains("\"text\"", body);
        }

        [UnityTest]
        public IEnumerator ARefusalArrivesAsAFailureWithItsReason()
        {
            // A client that only works when the server agrees is not finished.
            string failure = null, body = null;
            _client.Failed += reason => failure = reason;
            _client.Spoke += json => body = json;

            // A misspelled field: the service answers 400 with {error, code}.
            _client.SendEvent("", "{}");
            yield return Until(() => failure != null || body != null, 15f);

            Assert.IsNotNull(failure,
                "an invalid request was not reported as a failure; the client "
                + "swallowed it");
            StringAssert.Contains("400", failure,
                "the failure does not carry the status the service returned");
        }

        [UnityTest]
        public IEnumerator TheWorldCanBeSavedAndInspected()
        {
            string blob = null, report = null, failure = null;
            _client.StateExported += json => blob = json;
            _client.StateReport += json => report = json;
            _client.Failed += reason => failure = reason;

            _client.ExportState();
            yield return Until(() => blob != null || failure != null);
            Assert.IsNull(failure, "export failed: " + failure);
            Assert.IsNotNull(blob, "no save blob within the timeout");
            StringAssert.Contains("unscripted-state", blob,
                "the export is not a state blob");

            // And the thing a load screen actually does: ask before committing.
            _client.InspectState(blob);
            yield return Until(() => report != null || failure != null);
            Assert.IsNull(failure, "inspect failed: " + failure);
            StringAssert.Contains("\"usable\"", report,
                "inspect did not answer whether the save is usable");
        }
    }
}
