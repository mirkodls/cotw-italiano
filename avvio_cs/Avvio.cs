// AVVIO di CotW Italiano, versione C# (.NET Framework 4, gia' presente su ogni Windows 10/11: nessuna installazione).
// Fa ESATTAMENTE quello che faceva avvio/principale.py (stesse cartelle, stesso stato.json, stessi argomenti), ma e'
// un exe piccolo che parte subito e che gli antivirus bloccano molto meno di un exe fatto con Python.
//
//   <installazione>\CotW Italiano.exe            <- questo AVVIO
//   <installazione>\programma\<versione>\...      <- programma vero (una cartella per versione)
//   <installazione>\programma\stato.json          <- attuale, precedente, in_prova, rotte, rinvio
//
// Regole (AGGIORNAMENTI_SICURI.txt): 1 aggiornatore separato; 2 si aggiorna da solo in due copie (scarica accanto,
// prova, poi scambia); 3 la versione nuova deve dire "sono ok" (avvio_ok.txt), altrimenti si torna alla precedente;
// 4 scarica solo cio' che e' in online.json con la FIRMA Ed25519 dell'autore e l'impronta SHA-256 giusta;
// 7 se qualcosa va storto c'e' sempre il link per scaricare a mano.
// Si compila con il csc.exe di .NET Framework (C# 5): niente sintassi nuova.
using System;
using System.Collections;
using System.Collections.Generic;
using System.Diagnostics;
using System.Globalization;
using System.IO;
using System.IO.Compression;
using System.Net;
using System.Numerics;
using System.Reflection;
using System.Security.Cryptography;
using System.Text;
using System.Text.RegularExpressions;
using System.Threading;
using System.Web.Script.Serialization;
using System.Windows.Forms;

[assembly: AssemblyTitle("CotW Italiano - avvio e aggiornamenti")]
[assembly: AssemblyProduct("CotW Italiano")]
[assembly: AssemblyCompany("Mirko Del Sette")]
[assembly: AssemblyCopyright("(C) Mirko Del Sette - GPL-3.0")]
[assembly: AssemblyVersion("2.0.0.0")]
[assembly: AssemblyFileVersion("2.0.0.0")]

namespace CotWItaliano
{
    static class Avvio
    {
        public const string AVVIO_VERSIONE = "2";      // deve essere uguale a avvio/__init__.py (lo controlla la build)
        const string NOME_EXE = "CotW Italiano.exe";
        const string NOME_APP = "CotW Italiano";
        const string REPO = "mirkodls/cotw-italiano";
        const string SITO_SCARICA = "https://github.com/mirkodls/cotw-italiano#-scarica";
        const string FILE_OK = "avvio_ok.txt";
        static readonly string[] CHIAVI_PUBBLICHE = {
            "71c92d55e9385fd2c54c93b39eab21ad24698bd82f49824cfc281977f8790d76",   // Mirko Del Sette, 05/11/2026
        };
        static readonly bool PROVA = Env("COTW_AVVIO_PROVA") == "1";
        static readonly JavaScriptSerializer JSON = new JavaScriptSerializer { MaxJsonLength = int.MaxValue };

        static string Env(string n) { return Environment.GetEnvironmentVariable(n); }

        // ---------------- cartelle e stato ----------------
        static string ExeAvvio()
        {
            string e = Env("COTW_AVVIO_EXE");
            return Path.GetFullPath(string.IsNullOrEmpty(e) ? Assembly.GetEntryAssembly().Location : e);
        }
        static string CartellaApp() { return Path.GetDirectoryName(ExeAvvio()); }
        static string CartellaProgrammi() { return Path.Combine(CartellaApp(), "programma"); }

        static string DatiApp()
        {
            string b = Env("COTW_DATI");
            if (string.IsNullOrEmpty(b)) b = Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData);
            string d = Path.Combine(b, NOME_APP);
            Directory.CreateDirectory(d);
            return d;
        }

        static void Registro(string t)
        {
            try
            {
                File.AppendAllText(Path.Combine(DatiApp(), "avvio.log"),
                    DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss") + "  [C#] " + t + "\r\n", Encoding.UTF8);
            }
            catch { }
        }

        static int[] Num(object v)
        {
            try
            {
                string s = Convert.ToString(v, CultureInfo.InvariantCulture);
                string[] p = s.Split('.');
                int[] r = new int[p.Length];
                for (int i = 0; i < p.Length; i++) r[i] = int.Parse(p[i], CultureInfo.InvariantCulture);
                return r;
            }
            catch { return new int[] { 0 }; }
        }

        static int Confronta(object a, object b)       // come il confronto delle tuple in Python
        {
            int[] x = Num(a), y = Num(b);
            for (int i = 0; i < Math.Min(x.Length, y.Length); i++)
                if (x[i] != y[i]) return x[i] < y[i] ? -1 : 1;
            return x.Length.CompareTo(y.Length);
        }

        static List<string> Versioni()
        {
            List<string> out_ = new List<string>();
            try
            {
                foreach (string d in Directory.GetDirectories(CartellaProgrammi()))
                {
                    string n = Path.GetFileName(d);
                    if (Regex.IsMatch(n, @"^\d+(\.\d+)*$") && File.Exists(Path.Combine(d, NOME_EXE))) out_.Add(n);
                }
            }
            catch { }
            out_.Sort(delegate (string a, string b) { return Confronta(b, a); });
            return out_;
        }

        static string FileStato() { return Path.Combine(CartellaProgrammi(), "stato.json"); }

        static Dictionary<string, object> LeggiStato()
        {
            try
            {
                Dictionary<string, object> s = JSON.DeserializeObject(File.ReadAllText(FileStato(), Encoding.UTF8))
                    as Dictionary<string, object>;
                if (s != null) return s;
            }
            catch { }
            return new Dictionary<string, object>();
        }

        static void SalvaStato(Dictionary<string, object> s)
        {
            Directory.CreateDirectory(CartellaProgrammi());
            string tmp = FileStato() + ".tmp";
            File.WriteAllText(tmp, JSON.Serialize(s), new UTF8Encoding(false));
            if (File.Exists(FileStato())) File.Replace(tmp, FileStato(), null);
            else File.Move(tmp, FileStato());
        }

        static string S(Dictionary<string, object> d, string k)
        {
            object v;
            return d != null && d.TryGetValue(k, out v) && v != null ? Convert.ToString(v, CultureInfo.InvariantCulture) : null;
        }

        static List<string> Rotte(Dictionary<string, object> s)
        {
            List<string> r = new List<string>();
            object v;
            if (s.TryGetValue("rotte", out v) && v is IEnumerable && !(v is string))
                foreach (object x in (IEnumerable)v) if (x != null) r.Add(x.ToString());
            return r;
        }

        static string ScegliVersione(Dictionary<string, object> s)
        {
            List<string> presenti = Versioni();
            List<string> rotte = Rotte(s);
            List<string> buone = presenti.FindAll(delegate (string v) { return !rotte.Contains(v); });
            string att = presenti.Contains(S(s, "attuale") ?? "") ? S(s, "attuale") : null;
            if (buone.Count > 0 && (att == null || Confronta(buone[0], att) > 0))
            {
                string nuova = buone[0];
                if (att != null && att != nuova) s["precedente"] = att;
                else if (!presenti.Contains(S(s, "precedente") ?? "")) s.Remove("precedente");
                s["attuale"] = nuova;
                s["in_prova"] = nuova;
                SalvaStato(s);
                Registro("versione nuova in prova: " + nuova + " (precedente " + (S(s, "precedente") ?? "-") + ")");
            }
            else if (att == null && presenti.Count > 0)
            {
                s["attuale"] = presenti[0];
                SalvaStato(s);
            }
            return S(s, "attuale");
        }

        static void Cancella(string d) { try { if (Directory.Exists(d)) Directory.Delete(d, true); } catch { } }

        static void PulisciVecchie(Dictionary<string, object> s)
        {
            string att = S(s, "attuale"), prec = S(s, "precedente");
            List<string> rotte = Rotte(s);
            foreach (string v in Versioni())
                if (v != att && v != prec && !rotte.Contains(v)) Cancella(Path.Combine(CartellaProgrammi(), v));
            List<string> resto = new List<string>();
            foreach (string v in rotte)
            {
                if (Confronta(v, att) < 0) Cancella(Path.Combine(CartellaProgrammi(), v));
                else resto.Add(v);
            }
            s["rotte"] = resto.ToArray();
            Cancella(Path.Combine(CartellaProgrammi(), "_scarico"));
        }

        // ---------------- finestre ----------------
        static bool Chiedi(string titolo, string testo)
        {
            if (PROVA) { Registro("[prova] domanda: " + titolo + " -> si"); return true; }
            return MessageBox.Show(testo, titolo, MessageBoxButtons.YesNo, MessageBoxIcon.Question) == DialogResult.Yes;
        }

        static void Avvisa(string titolo, string testo, bool conLink)
        {
            Registro("avviso: " + titolo + ": " + testo.Replace("\n", " "));
            if (PROVA) return;
            if (conLink)
            {
                if (MessageBox.Show(testo + "\n\nApro la pagina per scaricarlo a mano?", titolo, MessageBoxButtons.YesNo,
                        MessageBoxIcon.Warning) == DialogResult.Yes)
                    try { Process.Start(SITO_SCARICA); } catch { }
            }
            else MessageBox.Show(testo, titolo, MessageBoxButtons.OK, MessageBoxIcon.Warning);
        }

        class Barra
        {
            Form f; Label testo; ProgressBar barra;
            volatile string t = "..."; long fatti, totale;
            public Barra(string titolo)
            {
                if (PROVA) return;
                f = new Form();
                f.Text = titolo; f.FormBorderStyle = FormBorderStyle.FixedDialog; f.MaximizeBox = false; f.MinimizeBox = false;
                f.ControlBox = false; f.StartPosition = FormStartPosition.CenterScreen; f.ClientSize = new System.Drawing.Size(460, 90);
                testo = new Label(); testo.SetBounds(16, 14, 428, 22); testo.Text = "...";
                barra = new ProgressBar(); barra.SetBounds(16, 46, 428, 22); barra.Maximum = 1000;
                f.Controls.Add(testo); f.Controls.Add(barra);
                f.Show(); Application.DoEvents();
            }
            public void Imposta(string testo_, long a, long b) { t = testo_; Interlocked.Exchange(ref fatti, a); Interlocked.Exchange(ref totale, b); }
            public void Imposta(string testo_) { Imposta(testo_, 0, 0); }
            public void Esegui(Action<Barra> lavoro)
            {
                Exception errore = null;
                Thread th = new Thread(delegate () { try { lavoro(this); } catch (Exception e) { errore = e; } });
                th.IsBackground = true;
                th.Start();
                while (!th.Join(100))
                {
                    if (f == null) continue;
                    testo.Text = t;
                    long b = Interlocked.Read(ref totale);
                    barra.Value = b > 0 ? (int)Math.Min(1000, Interlocked.Read(ref fatti) * 1000 / b) : 0;
                    Application.DoEvents();
                }
                if (f != null) f.Close();
                if (errore != null) throw errore;
            }
        }

        // ---------------- internet ----------------
        static HttpWebResponse Apri(string url, int timeoutMs, bool noCache)
        {
            HttpWebRequest r = (HttpWebRequest)WebRequest.Create(url);
            r.UserAgent = "CotW-Italiano-Avvio/" + AVVIO_VERSIONE + " (https://github.com/" + REPO + ")";
            r.Timeout = timeoutMs; r.ReadWriteTimeout = Math.Max(timeoutMs, 60000);
            r.AllowAutoRedirect = true;
            if (noCache) r.Headers["Cache-Control"] = "no-cache";
            return (HttpWebResponse)r.GetResponse();
        }

        static string UrlOnline()
        {
            string u = Env("COTW_URL_ONLINE");
            return string.IsNullOrEmpty(u) ? "https://raw.githubusercontent.com/" + REPO + "/main/online.json" : u;
        }

        static Dictionary<string, object> LeggiOnline(int timeoutMs)
        {
            try
            {
                using (HttpWebResponse r = Apri(UrlOnline(), timeoutMs, true))
                using (StreamReader sr = new StreamReader(r.GetResponseStream(), Encoding.UTF8))
                {
                    Dictionary<string, object> o = JSON.DeserializeObject(sr.ReadToEnd()) as Dictionary<string, object>;
                    return o ?? new Dictionary<string, object>();
                }
            }
            catch (Exception e)
            {
                Registro("online.json non letto: " + e.Message);
                return new Dictionary<string, object>();
            }
        }

        static string[] Chiavi()
        {
            string k = Env("COTW_AVVIO_CHIAVE_PROVA");
            if (PROVA && !string.IsNullOrEmpty(k)) return new string[] { k };
            return CHIAVI_PUBBLICHE;
        }

        static string Canale()
        {
            try
            {
                Dictionary<string, object> c = JSON.DeserializeObject(File.ReadAllText(Path.Combine(DatiApp(), "impostazioni.json"),
                    Encoding.UTF8)) as Dictionary<string, object>;
                return S(c, "canale") == "anteprima" ? "anteprima" : "normale";
            }
            catch { return "normale"; }
        }

        static Dictionary<string, object> VersioneNuova(Dictionary<string, object> online, string attuale, List<string> rotte)
        {
            List<string> blocchi = new List<string> { "programma" };
            if (Canale() == "anteprima") blocchi.Add("anteprima");
            Dictionary<string, object> migliore = null;
            foreach (string nome in blocchi)
            {
                object o;
                if (!online.TryGetValue(nome, out o)) continue;
                Dictionary<string, object> p = o as Dictionary<string, object>;
                if (p == null || S(p, "versione") == null || S(p, "url") == null || S(p, "sha256") == null) continue;
                string v = S(p, "versione");
                if (!Regex.IsMatch(v, @"^\d+(\.\d+)*$") || rotte.Contains(v) || Confronta(v, attuale) <= 0) continue;
                if (!Firma.Firmato(p, Chiavi())) { Registro("versione " + v + " online senza firma valida: ignorata"); continue; }
                if (migliore == null || Confronta(v, S(migliore, "versione")) > 0) migliore = p;
            }
            return migliore;
        }

        static string Scarica(string url, string dest, string sha, Barra barra, string testo)
        {
            Directory.CreateDirectory(Path.GetDirectoryName(dest));
            string part = dest + ".part";
            using (SHA256 h = SHA256.Create())
            {
                using (HttpWebResponse r = Apri(url, 60000, false))
                using (Stream s = r.GetResponseStream())
                using (FileStream f = new FileStream(part, FileMode.Create, FileAccess.Write))
                {
                    long tot = r.ContentLength > 0 ? r.ContentLength : 0, fatti = 0;
                    byte[] buf = new byte[1 << 18];
                    int n;
                    while ((n = s.Read(buf, 0, buf.Length)) > 0)
                    {
                        f.Write(buf, 0, n);
                        h.TransformBlock(buf, 0, n, null, 0);
                        fatti += n;
                        if (barra != null)
                            barra.Imposta(testo + ": " + (fatti >> 20) + " di " + Math.Max(tot >> 20, 1) + " MB", fatti, tot);
                    }
                    h.TransformFinalBlock(new byte[0], 0, 0);
                }
                if (Hex(h.Hash) != (sha ?? "").ToLowerInvariant())
                {
                    File.Delete(part);
                    throw new Exception("Il file scaricato e' rovinato (impronta sbagliata). Riprova piu' tardi.");
                }
            }
            if (File.Exists(dest)) File.Delete(dest);
            File.Move(part, dest);
            return dest;
        }

        static string Hex(byte[] b)
        {
            StringBuilder sb = new StringBuilder(b.Length * 2);
            foreach (byte x in b) sb.Append(x.ToString("x2"));
            return sb.ToString();
        }

        // ---------------- aggiornamento ----------------
        static string InstallaVersione(Dictionary<string, object> info, Barra barra)
        {
            string v = S(info, "versione");
            string base_ = Path.Combine(CartellaProgrammi(), "_scarico");
            Cancella(base_);
            string zp = Scarica(S(info, "url"), Path.Combine(base_, "programma.zip"), S(info, "sha256"), barra,
                                "Scarico la versione " + v);
            barra.Imposta("Controllo e preparo la versione " + v + "...");
            string est = Path.Combine(base_, "estratto");
            string radice = Path.GetFullPath(est) + Path.DirectorySeparatorChar;
            using (ZipArchive z = ZipFile.OpenRead(zp))
            {
                foreach (ZipArchiveEntry m in z.Entries)
                {
                    string n = m.FullName.Replace('\\', '/');
                    if (n.StartsWith("/") || n.Contains(":") || Array.IndexOf(n.Split('/'), "..") >= 0)
                        throw new Exception("Pacchetto del programma non valido.");
                    string out_ = Path.GetFullPath(Path.Combine(est, n.Replace('/', Path.DirectorySeparatorChar)));
                    if (!out_.StartsWith(radice, StringComparison.OrdinalIgnoreCase))
                        throw new Exception("Pacchetto del programma non valido.");
                    if (n.EndsWith("/")) { Directory.CreateDirectory(out_); continue; }
                    Directory.CreateDirectory(Path.GetDirectoryName(out_));
                    m.ExtractToFile(out_, true);
                }
            }
            string sorgente = null;
            foreach (string f in Directory.GetFiles(est, NOME_EXE, SearchOption.AllDirectories)) { sorgente = Path.GetDirectoryName(f); break; }
            if (sorgente == null) throw new Exception("Nel pacchetto scaricato manca " + NOME_EXE + ".");
            string dest = Path.Combine(CartellaProgrammi(), v);
            if (Directory.Exists(dest)) Directory.Delete(dest, true);
            Directory.Move(sorgente, dest);
            Cancella(base_);
            Registro("versione " + v + " scaricata in " + dest);
            return v;
        }

        static string AggiornaAvvio(Dictionary<string, object> info, Barra barra)
        {
            object o;
            if (!info.TryGetValue("avvio", out o)) return null;
            Dictionary<string, object> a = o as Dictionary<string, object>;
            if (a == null || S(a, "url") == null || S(a, "sha256") == null) return null;
            if (Confronta(S(a, "versione"), AVVIO_VERSIONE) <= 0) return null;
            string io = ExeAvvio();
            string nuovo = Path.Combine(CartellaApp(), "CotW Italiano.new.exe");
            string vecchio = Path.Combine(CartellaApp(), "CotW Italiano.old.exe");
            Scarica(S(a, "url"), nuovo, S(a, "sha256"), barra, "Scarico l'avvio " + S(a, "versione"));
            barra.Imposta("Provo l'avvio nuovo...");
            string rap = Path.Combine(DatiApp(), "prova_avvio_nuovo.json");
            try
            {
                if (File.Exists(rap)) File.Delete(rap);
                ProcessStartInfo psi = new ProcessStartInfo(nuovo, Unisci(new string[] { "--prova-avvio", rap, "--senza-internet" }));
                psi.UseShellExecute = false; psi.CreateNoWindow = true;
                using (Process p = Process.Start(psi))
                {
                    if (!p.WaitForExit(180000)) { try { p.Kill(); } catch { } throw new Exception("tempo scaduto"); }
                    Dictionary<string, object> esito = JSON.DeserializeObject(File.ReadAllText(rap, Encoding.UTF8)) as Dictionary<string, object>;
                    object ok;
                    if (p.ExitCode != 0 || esito == null || !esito.TryGetValue("ok", out ok) || !(ok is bool) || !(bool)ok)
                        throw new Exception("la prova dell'avvio nuovo non e' riuscita");
                }
            }
            catch (Exception e)
            {
                Registro("avvio nuovo " + S(a, "versione") + " scartato: " + e.Message);
                try { File.Delete(nuovo); } catch { }
                return null;
            }
            try
            {
                if (File.Exists(vecchio)) File.Delete(vecchio);
                File.Move(io, vecchio);                // Windows permette di rinominare un exe acceso
                try { File.Move(nuovo, io); }
                catch { File.Move(vecchio, io); throw; }
            }
            catch (Exception e)
            {
                Registro("scambio dell'avvio non riuscito: " + e.Message);
                return null;
            }
            Registro("avvio aggiornato alla " + S(a, "versione") + " (riserva: " + vecchio + ")");
            return S(a, "versione");
        }

        static bool Aggiorna(Dictionary<string, object> info)
        {
            try
            {
                new Barra("Aggiornamento di CotW Italiano").Esegui(delegate (Barra b) { InstallaVersione(info, b); });
            }
            catch (Exception e)
            {
                Avvisa("Aggiornamento non riuscito", "Non sono riuscito ad aggiornare CotW Italiano alla versione " +
                       S(info, "versione") + ":\n" + e.Message + "\n\nIl programma continua a funzionare come prima.", true);
                return false;
            }
            try
            {
                new Barra("Aggiornamento di CotW Italiano").Esegui(delegate (Barra b) { AggiornaAvvio(info, b); });
            }
            catch (Exception e) { Registro("aggiornamento dell'avvio saltato: " + e.Message); }
            return true;
        }

        static double Ora() { return (DateTime.UtcNow - new DateTime(1970, 1, 1, 0, 0, 0, DateTimeKind.Utc)).TotalSeconds; }

        static bool ControllaOnline(Dictionary<string, object> s, string attuale, bool forza)
        {
            Dictionary<string, object> online = LeggiOnline(4000);
            if (online.Count == 0) return false;
            Dictionary<string, object> info = VersioneNuova(online, attuale, Rotte(s));
            if (info == null) return false;
            object ro;
            Dictionary<string, object> rin = s.TryGetValue("rinvio", out ro) ? ro as Dictionary<string, object> : null;
            if (!forza && rin != null && S(rin, "versione") == S(info, "versione"))
            {
                double fino = 0;
                try { fino = Convert.ToDouble(rin["fino"], CultureInfo.InvariantCulture); } catch { }
                if (Ora() < fino) return false;
            }
            StringBuilder nov = new StringBuilder();
            object n;
            if (info.TryGetValue("novita", out n) && n is IEnumerable && !(n is string))
            {
                int i = 0;
                foreach (object x in (IEnumerable)n) { if (i++ >= 6) break; nov.Append("\n - ").Append(x); }
            }
            if (!forza && !Chiedi("Aggiornamento di CotW Italiano", "E' uscita la versione " + S(info, "versione") +
                    " di CotW Italiano (tu hai la " + attuale + ")." + (nov.Length > 0 ? "\n\nNovita':" + nov : "") +
                    "\n\nAggiorno adesso? Ci vuole un minuto."))
            {
                Dictionary<string, object> r = new Dictionary<string, object>();
                r["versione"] = S(info, "versione");
                r["fino"] = Ora() + 86400;
                s["rinvio"] = r;
                SalvaStato(s);
                return false;
            }
            return Aggiorna(info);
        }

        // ---------------- apertura del programma, con ritorno indietro ----------------
        static string Quota(string a)                  // regole di Windows per gli argomenti (CommandLineToArgvW)
        {
            if (a.Length > 0 && a.IndexOfAny(new char[] { ' ', '\t', '"' }) < 0) return a;
            StringBuilder sb = new StringBuilder("\"");
            int bs = 0;
            foreach (char c in a)
            {
                if (c == '\\') { bs++; continue; }
                if (c == '"') { sb.Append('\\', bs * 2 + 1).Append('"'); bs = 0; continue; }
                sb.Append('\\', bs).Append(c); bs = 0;
            }
            sb.Append('\\', bs * 2).Append('"');
            return sb.ToString();
        }

        static string Unisci(IEnumerable<string> a)
        {
            List<string> q = new List<string>();
            foreach (string x in a) q.Add(Quota(x));
            return string.Join(" ", q.ToArray());
        }

        // codice di uscita, esito: "ok" | "rotta" | null
        static int Apri(string versione, List<string> argomenti, bool inProva, out string esito)
        {
            esito = null;
            string cart = Path.Combine(CartellaProgrammi(), versione);
            string ok = Path.Combine(cart, FILE_OK);
            if (inProva) try { File.Delete(ok); } catch { }
            Registro("apro " + versione + " " + string.Join(" ", argomenti.ToArray()) + (inProva ? " (in prova)" : ""));
            ProcessStartInfo psi = new ProcessStartInfo(Path.Combine(cart, NOME_EXE), Unisci(argomenti));
            psi.UseShellExecute = false;
            psi.EnvironmentVariables["COTW_AVVIO"] = ExeAvvio();
            psi.EnvironmentVariables["COTW_AVVIO_VERSIONE"] = AVVIO_VERSIONE;
            Process p;
            try { p = Process.Start(psi); }
            catch (Exception e)
            {
                Registro("la versione " + versione + " non si apre: " + e.Message);
                esito = "rotta";
                return -1;
            }
            using (p)
            {
                if (!inProva) { p.WaitForExit(); return p.ExitCode; }
                while (true)
                {
                    if (File.Exists(ok)) { p.WaitForExit(); esito = "ok"; return p.ExitCode; }
                    if (p.WaitForExit(300))
                    {
                        if (File.Exists(ok)) { esito = "ok"; return p.ExitCode; }
                        esito = p.ExitCode != 0 ? "rotta" : null;
                        return p.ExitCode;
                    }
                }
            }
        }

        static void TornaIndietro(Dictionary<string, object> s, string rotta, int codice)
        {
            List<string> rotte = Rotte(s);
            if (!rotte.Contains(rotta)) rotte.Add(rotta);
            s["rotte"] = rotte.ToArray();
            string prec = S(s, "precedente");
            s["in_prova"] = null;
            if (prec != null && Versioni().Contains(prec)) s["attuale"] = prec; else s.Remove("attuale");
            s.Remove("precedente");
            SalvaStato(s);
            Registro("versione " + rotta + " rotta (codice " + codice + "): torno alla " + (S(s, "attuale") ?? "-"));
            Avvisa("Versione nuova non partita", "La versione " + rotta + " di CotW Italiano non e' partita (errore " + codice +
                   ").\n\nTorno da solo alla versione di prima (" + (S(s, "attuale") ?? "-") + "): funziona come prima. " +
                   "L'errore e' stato segnato, la versione rotta non verra' piu' proposta.", S(s, "attuale") == null);
        }

        static int EseguiProgramma(List<string> argomenti)
        {
            Dictionary<string, object> s = LeggiStato();
            for (int giro = 0; giro < 3; giro++)
            {
                string v = ScegliVersione(s);
                if (v == null)
                {
                    Avvisa("CotW Italiano", "Non trovo il programma nella cartella di installazione:\n" + CartellaProgrammi() +
                           "\n\nReinstallalo dal sito ufficiale.", true);
                    return 1;
                }
                bool inProva = S(s, "in_prova") == v;
                string esito;
                int codice = Apri(v, argomenti, inProva, out esito);
                if (esito == "ok")
                {
                    s = LeggiStato();
                    s["in_prova"] = null;
                    SalvaStato(s);
                    Registro("versione " + v + " confermata (sono ok)");
                    try { PulisciVecchie(s); SalvaStato(s); } catch { }
                    return codice;
                }
                if (esito == "rotta")
                {
                    s = LeggiStato();
                    bool altre = false;
                    foreach (string x in Versioni()) if (x != v) altre = true;
                    if (altre) { TornaIndietro(s, v, codice); continue; }
                    Avvisa("CotW Italiano", "Il programma non si apre (" + codice + ").\n\nReinstallalo dal sito ufficiale.", true);
                    return 1;
                }
                return codice;
            }
            return 1;
        }

        // ---------------- prova dell'avvio (scambio in due copie e GitHub) ----------------
        static int ProvaAvvio(string[] argv)
        {
            int i = Array.IndexOf(argv, "--prova-avvio");
            string uscita = i + 1 < argv.Length ? argv[i + 1] : "prova_avvio.json";
            List<Dictionary<string, object>> passi = new List<Dictionary<string, object>>();
            Action<string, Func<string>> passo = delegate (string nome, Func<string> fn)
            {
                Dictionary<string, object> d = new Dictionary<string, object>();
                d["nome"] = nome;
                try { d["info"] = fn(); d["ok"] = true; }
                catch (Exception e) { d["ok"] = false; d["errore"] = e.GetType().Name + ": " + e.Message; }
                passi.Add(d);
            };
            passo("verifica firme (RFC 8032)", delegate
            {
                // vettore di prova 1 dell'RFC 8032 (messaggio vuoto)
                byte[] pub = DaHex("d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a");
                byte[] sig = DaHex("e5564300c360ac729086e2cc806e828a84877f1eb8e5d974d873e065224901555fb8821590a33bacc61e39701cf9b46bd25bf5f0595bbe24655141438e7a100b");
                if (!Firma.Verifica(pub, new byte[0], sig)) throw new Exception("la firma giusta non viene riconosciuta");
                sig[10] ^= 1;
                if (Firma.Verifica(pub, new byte[0], sig)) throw new Exception("una firma sbagliata viene accettata");
                return "ok";
            });
            passo("JSON come Python", delegate
            {
                Dictionary<string, object> d = JSON.DeserializeObject("{\"b\":[1,\"à\\n\\\"x\\\\\"],\"a\":{\"z\":true,\"y\":null}}")
                    as Dictionary<string, object>;
                string c = Encoding.UTF8.GetString(Firma.Canonico(d));
                string atteso = "{\"a\":{\"y\":null,\"z\":true},\"b\":[1,\"à\\n\\\"x\\\\\"]}";
                if (c != atteso) throw new Exception("formato diverso: " + c);
                return "ok";
            });
            if (Array.IndexOf(argv, "--senza-internet") < 0)
            {
                passo("online.json + firma", delegate
                {
                    Dictionary<string, object> o = LeggiOnline(30000);
                    object sv;
                    if (!o.TryGetValue("servizi", out sv) || !Firma.Firmato(sv as Dictionary<string, object>, CHIAVI_PUBBLICHE))
                        throw new Exception("online.json non letto o firma non verificata");
                    object pr;
                    string v = o.TryGetValue("programma", out pr) ? S(pr as Dictionary<string, object>, "versione") : "-";
                    if (pr != null && !Firma.Firmato(pr as Dictionary<string, object>, CHIAVI_PUBBLICHE))
                        throw new Exception("il blocco programma non risulta firmato");
                    return "programma online " + v;
                });
            }
            if (Env("COTW_AVVIO_SENZA_TK") == null)
            {
                passo("finestre", delegate
                {
                    using (Form f = new Form()) { IntPtr h = f.Handle; return h != IntPtr.Zero ? "ok" : "?"; }
                });
            }
            bool tutto = passi.TrueForAll(delegate (Dictionary<string, object> d) { return (bool)d["ok"]; });
            Dictionary<string, object> r = new Dictionary<string, object>();
            r["avvio"] = AVVIO_VERSIONE; r["linguaggio"] = "C#"; r["ok"] = tutto; r["passi"] = passi.ToArray();
            File.WriteAllText(uscita, JSON.Serialize(r), new UTF8Encoding(false));
            return tutto ? 0 : 1;
        }

        static byte[] DaHex(string h)
        {
            byte[] b = new byte[h.Length / 2];
            for (int i = 0; i < b.Length; i++) b[i] = Convert.ToByte(h.Substring(i * 2, 2), 16);
            return b;
        }

        // ---------------- ingresso ----------------
        [STAThread]
        static int Main(string[] args)
        {
            try { ServicePointManager.SecurityProtocol |= (SecurityProtocolType)3072; } catch { }   // TLS 1.2
            if (!PROVA) try { Application.EnableVisualStyles(); } catch { }
            List<string> argv = new List<string>(args);
            argv.Insert(0, ExeAvvio());
            if (argv.Contains("--prova-avvio")) return ProvaAvvio(argv.ToArray());
            List<string> argomenti = new List<string>(args);
            try
            {
                Dictionary<string, object> s = LeggiStato();
                string v = ScegliVersione(s);
                if (argomenti.Contains("--aggiorna"))           // richiesto dal programma (pulsante Aggiorna)
                {
                    argomenti.RemoveAll(delegate (string x) { return x == "--aggiorna"; });
                    ControllaOnline(s, v ?? "0", true);
                }
                else if (v != null && (argomenti.Count == 0 || argomenti[0] == "--gioco"))
                    ControllaOnline(s, v, false);                // apertura normale o tasto Gioca: controllo veloce
            }
            catch (Exception e) { Registro("controllo aggiornamenti saltato: " + e.Message); }   // mai bloccare l'apertura
            return EseguiProgramma(argomenti);
        }
    }

    // ================= firma Ed25519 (solo verifica, RFC 8032) e JSON come Python =================
    static class Firma
    {
        static readonly BigInteger P = BigInteger.Pow(2, 255) - 19;
        static readonly BigInteger L = BigInteger.Pow(2, 252) + BigInteger.Parse("27742317777372353535851937790883648493");
        static readonly BigInteger D = Mod(-121665 * Inv(121666));
        static readonly BigInteger I = BigInteger.ModPow(2, (P - 1) / 4, P);
        static readonly BigInteger GY = Mod(4 * Inv(5));
        static readonly BigInteger[] G = Punto(RecuperaX(GY, 0).Value, GY);

        static BigInteger Mod(BigInteger a) { BigInteger r = a % P; return r.Sign < 0 ? r + P : r; }
        static BigInteger Inv(BigInteger x) { return BigInteger.ModPow(Mod(x), P - 2, P); }
        static BigInteger[] Punto(BigInteger x, BigInteger y) { return new BigInteger[] { x, y, 1, Mod(x * y) }; }

        static BigInteger[] Somma(BigInteger[] p, BigInteger[] q)
        {
            BigInteger a = Mod((p[1] - p[0]) * (q[1] - q[0]));
            BigInteger b = Mod((p[1] + p[0]) * (q[1] + q[0]));
            BigInteger c = Mod(p[3] * 2 * D * q[3]);
            BigInteger d = Mod(p[2] * 2 * q[2]);
            BigInteger e = b - a, f = d - c, g = d + c, h = b + a;
            return new BigInteger[] { Mod(e * f), Mod(g * h), Mod(f * g), Mod(e * h) };
        }

        static BigInteger[] Per(BigInteger s, BigInteger[] p)
        {
            BigInteger[] q = { 0, 1, 1, 0 };
            while (s.Sign > 0)
            {
                if (!s.IsEven) q = Somma(q, p);
                p = Somma(p, p);
                s >>= 1;
            }
            return q;
        }

        static bool Uguali(BigInteger[] p, BigInteger[] q)
        {
            return Mod(p[0] * q[2] - q[0] * p[2]).IsZero && Mod(p[1] * q[2] - q[1] * p[2]).IsZero;
        }

        static BigInteger? RecuperaX(BigInteger y, int segno)
        {
            if (y >= P) return null;
            BigInteger x2 = Mod((y * y - 1) * Inv(D * y * y + 1));
            if (x2.IsZero) { if (segno != 0) return null; return BigInteger.Zero; }
            BigInteger x = BigInteger.ModPow(x2, (P + 3) / 8, P);
            if (!Mod(x * x - x2).IsZero) x = Mod(x * I);
            if (!Mod(x * x - x2).IsZero) return null;
            if ((int)(x & 1) != segno) x = P - x;
            return x;
        }

        static BigInteger LittleEndian(byte[] b, int da, int n)
        {
            byte[] t = new byte[n + 1];
            Array.Copy(b, da, t, 0, n);
            return new BigInteger(t);                   // byte in piu' a zero = numero positivo
        }

        static BigInteger[] Decomprimi(byte[] b, int da)
        {
            BigInteger y = LittleEndian(b, da, 32);
            int segno = (int)(y >> 255);
            y &= (BigInteger.One << 255) - 1;
            BigInteger? x = RecuperaX(y, segno);
            if (!x.HasValue) return null;
            return Punto(x.Value, y);
        }

        public static bool Verifica(byte[] pub, byte[] msg, byte[] firma)
        {
            if (pub.Length != 32 || firma.Length != 64) return false;
            BigInteger[] A = Decomprimi(pub, 0);
            if (A == null) return false;
            BigInteger[] R = Decomprimi(firma, 0);
            if (R == null) return false;
            BigInteger s = LittleEndian(firma, 32, 32);
            if (s >= L) return false;
            byte[] tutto = new byte[64 + msg.Length];
            Array.Copy(firma, 0, tutto, 0, 32);
            Array.Copy(pub, 0, tutto, 32, 32);
            Array.Copy(msg, 0, tutto, 64, msg.Length);
            byte[] hh;
            using (SHA512 sha = SHA512.Create()) hh = sha.ComputeHash(tutto);
            BigInteger h = LittleEndian(hh, 0, 64) % L;
            return Uguali(Per(s, G), Somma(R, Per(h, A)));
        }

        public static bool Firmato(Dictionary<string, object> dati, string[] chiavi)
        {
            if (dati == null) return false;
            object fo;
            if (!dati.TryGetValue("firma", out fo) || !(fo is string)) return false;
            string fh = (string)fo;
            if (fh.Length != 128 || !Regex.IsMatch(fh, "^[0-9a-fA-F]+$")) return false;
            byte[] f = new byte[64];
            for (int i = 0; i < 64; i++) f[i] = Convert.ToByte(fh.Substring(i * 2, 2), 16);
            byte[] msg;
            try { msg = Canonico(dati); } catch { return false; }       // formato che non so riprodurre: non firmato
            foreach (string k in chiavi)
            {
                try
                {
                    if (k.Length != 64) continue;
                    byte[] pub = new byte[32];
                    for (int i = 0; i < 32; i++) pub[i] = Convert.ToByte(k.Substring(i * 2, 2), 16);
                    if (Verifica(pub, msg, f)) return true;
                }
                catch { }
            }
            return false;
        }

        // Stessi byte di Python: json.dumps(d senza 'firma', sort_keys=True, ensure_ascii=False, separators=(',', ':'))
        public static byte[] Canonico(Dictionary<string, object> dati)
        {
            StringBuilder sb = new StringBuilder();
            Dictionary<string, object> d = new Dictionary<string, object>();
            foreach (KeyValuePair<string, object> kv in dati) if (kv.Key != "firma") d[kv.Key] = kv.Value;
            Scrivi(d, sb);
            return new UTF8Encoding(false).GetBytes(sb.ToString());
        }

        static void Scrivi(object o, StringBuilder sb)
        {
            if (o == null) { sb.Append("null"); return; }
            if (o is bool) { sb.Append((bool)o ? "true" : "false"); return; }
            if (o is string) { Stringa((string)o, sb); return; }
            if (o is int || o is long || o is short || o is byte || o is uint || o is ulong)
            {
                sb.Append(Convert.ToString(o, CultureInfo.InvariantCulture)); return;
            }
            if (o is decimal || o is double || o is float)
                throw new FormatException("numeri con la virgola non previsti nei blocchi firmati");
            IDictionary<string, object> dict = o as IDictionary<string, object>;
            if (dict != null)
            {
                List<string> k = new List<string>(dict.Keys);
                k.Sort(string.CompareOrdinal);
                sb.Append('{');
                for (int i = 0; i < k.Count; i++)
                {
                    if (i > 0) sb.Append(',');
                    Stringa(k[i], sb); sb.Append(':'); Scrivi(dict[k[i]], sb);
                }
                sb.Append('}');
                return;
            }
            IEnumerable lista = o as IEnumerable;
            if (lista != null)
            {
                sb.Append('[');
                bool primo = true;
                foreach (object x in lista) { if (!primo) sb.Append(','); primo = false; Scrivi(x, sb); }
                sb.Append(']');
                return;
            }
            throw new FormatException("tipo non previsto: " + o.GetType().Name);
        }

        static void Stringa(string s, StringBuilder sb)
        {
            sb.Append('"');
            foreach (char c in s)
            {
                switch (c)
                {
                    case '"': sb.Append("\\\""); break;
                    case '\\': sb.Append("\\\\"); break;
                    case '\n': sb.Append("\\n"); break;
                    case '\r': sb.Append("\\r"); break;
                    case '\t': sb.Append("\\t"); break;
                    case '\b': sb.Append("\\b"); break;
                    case '\f': sb.Append("\\f"); break;
                    default:
                        if (c < 0x20) sb.Append("\\u").Append(((int)c).ToString("x4"));
                        else sb.Append(c);
                        break;
                }
            }
            sb.Append('"');
        }
    }
}
