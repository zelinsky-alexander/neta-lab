using System;
using System.Net.Http;
using System.Net.Security;
using System.Security.Cryptography;
using System.Security.Cryptography.X509Certificates;

namespace NetaLab004
{
    internal static class Program
    {
        private static int Main(string[] args)
        {
            string url = null;
            string expectedCertificateSha256 = null;
            string runId = null;

            for (int i = 0; i < args.Length; ++i)
            {
                if (args[i] == "--url" && i + 1 < args.Length)
                {
                    url = args[++i];
                }
                else if (args[i] == "--server-cert-sha256" && i + 1 < args.Length)
                {
                    expectedCertificateSha256 = NormalizeHex(args[++i]);
                }
                else if (args[i] == "--run-id" && i + 1 < args.Length)
                {
                    runId = args[++i];
                }
            }

            if (String.IsNullOrWhiteSpace(url) || String.IsNullOrWhiteSpace(expectedCertificateSha256))
            {
                Console.Error.WriteLine("Usage: neta-lab-004-payload.exe --url <https-url> --server-cert-sha256 <sha256> [--run-id <id>]");
                return 2;
            }

            try
            {
                using (HttpClientHandler handler = new HttpClientHandler())
                {
                    handler.ServerCertificateCustomValidationCallback = delegate(
                        HttpRequestMessage request,
                        X509Certificate2 certificate,
                        X509Chain chain,
                        SslPolicyErrors errors)
                    {
                        if (certificate == null)
                        {
                            return false;
                        }

                        string observed = ComputeSha256Hex(certificate.RawData);
                        return String.Equals(observed, expectedCertificateSha256, StringComparison.OrdinalIgnoreCase);
                    };

                    using (HttpClient client = new HttpClient(handler))
                    {
                        client.Timeout = TimeSpan.FromSeconds(15);
                        client.DefaultRequestHeaders.UserAgent.ParseAdd("NETA-Lab/004-Payload");
                        client.DefaultRequestHeaders.Add("X-NETA-Lab-Scenario", "NETA-LAB-004");
                        if (!String.IsNullOrWhiteSpace(runId))
                        {
                            client.DefaultRequestHeaders.Add("X-NETA-Lab-Run", runId);
                        }

                        HttpResponseMessage response = client.GetAsync(url).GetAwaiter().GetResult();
                        string body = response.Content.ReadAsStringAsync().GetAwaiter().GetResult();
                        if (!response.IsSuccessStatusCode)
                        {
                            Console.Error.WriteLine("NETA-LAB-004 callback failed: HTTP " + (int)response.StatusCode);
                            return 3;
                        }

                        Console.WriteLine("NETA-LAB-004 payload callback complete run_id=" + (runId ?? "") + " response=" + body.Trim());
                        return 0;
                    }
                }
            }
            catch (Exception ex)
            {
                Console.Error.WriteLine("NETA-LAB-004 payload error: " + ex.Message);
                return 4;
            }
        }

        private static string ComputeSha256Hex(byte[] bytes)
        {
            using (SHA256 sha256 = SHA256.Create())
            {
                byte[] digest = sha256.ComputeHash(bytes);
                return BitConverter.ToString(digest).Replace("-", String.Empty).ToLowerInvariant();
            }
        }

        private static string NormalizeHex(string value)
        {
            return (value ?? String.Empty).Replace(":", String.Empty).Replace("-", String.Empty).Trim().ToLowerInvariant();
        }
    }
}
