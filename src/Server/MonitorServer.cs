using System.Net;
using System.Net.Sockets;
using System.Text;
using System.Text.Json;
using Common;

namespace Server
{
    /// <summary>
    /// Server TCP cua chuong trinh: lang nghe ket noi, doc tung dong JSON,
    /// quan ly danh sach may tram, gui ACK, theo doi Online/Offline,
    /// gui thong bao NOTIFY (giai doan 3) va gui yeu cau REQUEST
    /// doi may tram tra loi (giai doan 4).
    ///
    /// Cach lam don gian, dung 3 loai luong (Thread):
    ///  - 1 luong cho vong lap chap nhan ket noi moi
    ///  - moi Client duoc phuc vu boi 1 luong rieng
    ///  - 1 luong dinh ky kiem tra may tram nao qua han khong gui thong diep (giai doan 2)
    ///    va yeu cau nao da cho qua lau (giai doan 4)
    /// </summary>
    public class MonitorServer
    {
        private TcpListener _listener;
        private Thread _acceptThread;
        private Thread _timeoutThread;
        private bool _running;

        // Moi lan Start() tang so nay len 1. Cac luong cua lan chay truoc (vong lap nhan ket noi,
        // vong lap kiem tra qua han) so sanh so da luu voi so hien tai de tu thoat.
        // Neu khong co so nay thi khi nguoi dung bam Dung roi Bat lai that nhanh, luong kiem tra
        // qua han cua lan chay truoc van con thuc (no dang ngu 1 giay) va sinh ra 2 vong lap
        // cung luc, moi lan Dung/Bat lai la bo lai them mot luong khong bao gio ket thuc.
        private int _runId;

        // Danh sach may tram, khoa (key) la ten may.
        private readonly Dictionary<string, StationInfo> _stations = new Dictionary<string, StationInfo>();

        // Khi nhieu luong cung doc/ghi _stations thi phai khoa lai cho an toan.
        private readonly object _lock = new object();

        // Giai doan 4: cac yeu cau da gui va dang cho may tram tra loi.
        // Khoa (key) la truong "id" cua thong diep REQUEST, nho vay khi nhan duoc
        // RESPONSE/ERROR ta biet no ung voi yeu cau nao va da gui tu bao lau.
        private readonly Dictionary<string, PendingRequest> _pending = new Dictionary<string, PendingRequest>();

        // Mot yeu cau dang cho tra loi.
        private class PendingRequest
        {
            public string StationName = "";
            public string Code = "";
            public DateTime SentAt = DateTime.Now;
        }

        // Su kien bao cho giao dien biet co chuyen xay ra.
        // (giao dien se tu chuyen ve luong UI bang Invoke)
        public event Action<string> Log;
        public event Action StationsChanged;

        // Giai doan 4: co ket qua tra loi cho mot yeu cau (ke ca truong hop loi).
        public event Action<RequestAnswer> AnswerReceived;

        /// <summary>Server dang chay hay khong.</summary>
        public bool IsRunning
        {
            get { return _running; }
        }

        /// <summary>Bat dau lang nghe tren cong da cho.</summary>
        public void Start(int port)
        {
            if (_running)
            {
                return;
            }

            // IPAddress.Any = lang nghe tren tat ca card mang cua may.
            _listener = new TcpListener(IPAddress.Any, port);
            _listener.Start();
            _running = true;

            int runId = ++_runId;

            _acceptThread = new Thread(() => AcceptLoop(runId));
            _acceptThread.IsBackground = true;
            _acceptThread.Start();

            // Giai doan 2: luong dinh ky kiem tra may tram bi timeout.
            _timeoutThread = new Thread(() => TimeoutLoop(runId));
            _timeoutThread.IsBackground = true;
            _timeoutThread.Start();

            RaiseLog("Server dang lang nghe tren cong " + port);
            RaiseLog("Chu ky HEARTBEAT: " + (Protocol.HeartbeatIntervalMs / 1000) + " giay"
                     + ", het han sau: " + (Protocol.OfflineTimeoutMs / 1000) + " giay.");
        }

        /// <summary>Dung Server va ngat tat ca ket noi.</summary>
        public void Stop()
        {
            _running = false;

            try
            {
                if (_listener != null)
                {
                    _listener.Stop();
                }
            }
            catch (Exception)
            {
                // Bo qua loi khi dung listener.
            }

            // Dong ket noi cua tat ca may tram.
            List<StationInfo> list = GetStations();
            foreach (StationInfo station in list)
            {
                try
                {
                    station.Client.Close();
                }
                catch (Exception)
                {
                }
            }

            // Cac yeu cau dang cho tra loi se khong bao gio co ket qua nua, vi Server da dung
            // nen luong kiem tra het han cung dung theo. Phai bao ngay cho giao dien biet,
            // khong de nguoi dung cho mai mot ket qua khong bao gio den.
            FailAllPendingRequests("Server da dung truoc khi may tram tra loi.");

            RaiseLog("Server da dung.");
        }

        /// <summary>Lay ban sao danh sach may tram (de giao dien hien thi).</summary>
        public List<StationInfo> GetStations()
        {
            lock (_lock)
            {
                return new List<StationInfo>(_stations.Values);
            }
        }

        /// <summary>Vong lap cho ket noi moi tu cac Client.</summary>
        private void AcceptLoop(int runId)
        {
            while (_running && runId == _runId)
            {
                TcpClient client;
                try
                {
                    client = _listener.AcceptTcpClient();
                }
                catch (Exception)
                {
                    // Khi Stop() goi _listener.Stop(), AcceptTcpClient se nem loi -> thoat vong lap.
                    break;
                }

                RaiseLog("Co ket noi moi tu " + client.Client.RemoteEndPoint);

                // Moi Client xu ly tren mot luong rieng de khong chan cac Client khac.
                Thread clientThread = new Thread(() => HandleClient(client));
                clientThread.IsBackground = true;
                clientThread.Start();
            }
        }

        /// <summary>
        /// Phuc vu mot Client: doc tung dong thong diep cho den khi Client ngat ket noi.
        /// </summary>
        private void HandleClient(TcpClient client)
        {
            // Lay IP that cua may tram tu ket noi TCP.
            string remoteIp = ((IPEndPoint)client.Client.RemoteEndPoint).Address.ToString();

            NetworkStream stream = client.GetStream();

            // Doc theo tung dong: StreamReader.ReadLine() doc cho den ky tu '\n'
            // nen dung luon voi dinh dang giao thuc.
            StreamReader reader = new StreamReader(stream, Encoding.UTF8, false);

            // Ghi cung theo tung dong. Phai dat NewLine = "\n" cho dung giao thuc
            // (mac dinh cua Windows la "\r\n").
            StreamWriter writer = new StreamWriter(stream, new UTF8Encoding(false));
            writer.AutoFlush = true;
            writer.NewLine = Protocol.LineEnd;

            // May tram cua ket noi nay. Chi co gia tri sau khi nhan duoc REGISTER.
            StationInfo station = null;

            try
            {
                string line;
                while ((line = reader.ReadLine()) != null)
                {
                    LanMessage msg;
                    try
                    {
                        msg = LanMessage.FromJson(line);
                    }
                    catch (JsonException)
                    {
                        // JSON sai dinh dang: ghi log roi bo qua dong nay.
                        RaiseLog("Nhan duoc JSON sai dinh dang: " + line);
                        continue;
                    }

                    if (msg.Type == MessageType.Register)
                    {
                        station = RegisterStation(msg, remoteIp, client, writer);
                    }
                    else if (msg.Type == MessageType.Heartbeat)
                    {
                        HandleHeartbeat(station, remoteIp);
                    }
                    else if (msg.Type == MessageType.Ack)
                    {
                        HandleAck(station, remoteIp, msg);
                    }
                    else if (msg.Type == MessageType.Response)
                    {
                        // Giai doan 4: may tram tra loi mot yeu cau.
                        HandleAnswer(station, remoteIp, msg, false);
                    }
                    else if (msg.Type == MessageType.Error)
                    {
                        // Giai doan 4: may tram bao khong xu ly duoc yeu cau.
                        HandleAnswer(station, remoteIp, msg, true);
                    }
                    else
                    {
                        // Cac loai khac (DISCONNECT...) se lam o giai doan sau.
                        RaiseLog("Nhan thong diep " + msg.Type + " tu " + msg.From);
                    }
                }
            }
            catch (Exception ex)
            {
                RaiseLog("Loi khi doc du lieu tu " + remoteIp + ": " + ex.Message);
            }
            finally
            {
                // Client ngat ket noi -> danh dau may tram la Offline.
                MarkOffline(station, remoteIp);

                try
                {
                    client.Close();
                }
                catch (Exception)
                {
                }
            }
        }

        /// <summary>
        /// Xu ly thong diep REGISTER: them/cap nhat may tram va gui ACK xac nhan.
        /// Tra ve may tram vua dang ky de dung cho cac thong diep sau nay.
        /// </summary>
        private StationInfo RegisterStation(LanMessage msg, string remoteIp, TcpClient client, StreamWriter writer)
        {
            // Ten may lay tu truong "from". Neu Client quen dat ten thi lay IP lam ten.
            string name = msg.From;
            if (string.IsNullOrEmpty(name))
            {
                name = remoteIp;
            }

            StationInfo station = new StationInfo();
            station.Name = name;

            // Lay IP tu ket noi TCP cho chac chan (Client khai bao IP trong "payload",
            // nhung IP cua ket noi moi la IP that su dang lien lac).
            station.Ip = remoteIp;
            station.Status = "Online";
            station.LastSeen = DateTime.Now;
            station.Client = client;
            station.Writer = writer;

            bool isNew;
            lock (_lock)
            {
                isNew = !_stations.ContainsKey(name);

                // Neu may nay da dang ky truoc do thi dong ket noi cu lai.
                if (!isNew)
                {
                    try
                    {
                        _stations[name].Client.Close();
                    }
                    catch (Exception)
                    {
                    }
                }

                _stations[name] = station;
            }

            RaiseLog("REGISTER tu " + name + " (IP ket noi: " + remoteIp + ", Client khai bao: " + msg.Payload + ")");

            // Gui ACK xac nhan da dang ky thanh cong.
            LanMessage ack = LanMessage.Create(MessageType.Ack, Protocol.ServerName, "REGISTER_OK");
            ack.Id = msg.Id;   // dat id ACK bang id cua REGISTER de Client doi chieu
            SendToStation(station, ack);

            RaiseLog("Da gui ACK cho " + name + (isNew ? " (may tram moi)." : " (cap nhat lai)."));

            RaiseStationsChanged();

            return station;
        }

        /// <summary>
        /// Xu ly thong diep HEARTBEAT (giai doan 2):
        /// cap nhat "lan lien lac cuoi" va dua may tram tro lai Online neu truoc do da Offline.
        /// </summary>
        private void HandleHeartbeat(StationInfo station, string remoteIp)
        {
            if (station == null)
            {
                // HEARTBEAT gui truoc khi REGISTER -> khong biet la may nao, bo qua.
                RaiseLog("Nhan HEARTBEAT tu " + remoteIp + " nhung may tram chua REGISTER.");
                return;
            }

            bool backOnline = false;

            lock (_lock)
            {
                station.LastSeen = DateTime.Now;

                if (station.Status != "Online")
                {
                    station.Status = "Online";
                    backOnline = true;
                }
            }

            if (backOnline)
            {
                RaiseLog("May tram " + station.Name + " da tro lai Online.");
            }

            // Bao giao dien ve lai bang de cap nhat cot "Lan lien lac cuoi".
            RaiseStationsChanged();
        }

        /// <summary>
        /// Xu ly ACK do may tram gui ve (giai doan 3).
        /// Khi nhan duoc NOTIFY, may tram tra ACK voi cung truong "id"
        /// nen Server biet chac chan thong bao da den noi.
        /// </summary>
        private void HandleAck(StationInfo station, string remoteIp, LanMessage msg)
        {
            if (station == null)
            {
                RaiseLog("Nhan ACK tu " + remoteIp + " nhung may tram chua REGISTER.");
                return;
            }

            // Ngay ca khi chi doc thong diep cung tinh la mot lan lien lac.
            lock (_lock)
            {
                station.LastSeen = DateTime.Now;
            }

            RaiseLog("May tram " + station.Name + " da xac nhan " + msg.Payload
                     + " (id=" + msg.Id + ")");
        }

        /// <summary>
        /// Giai doan 4: gui mot yeu cau (REQUEST) toi mot may tram.
        /// Server ghi lai yeu cau dang cho de lat nua ghep voi cau tra loi theo truong "id".
        /// </summary>
        public bool SendRequest(StationInfo station, string code)
        {
            LanMessage msg = LanMessage.Create(MessageType.Request, Protocol.ServerName, code);

            // Ghi vao danh sach cho TRUOC khi gui: neu may tram tra loi rat nhanh
            // thi cau tra loi co the den truoc khi ta kip ghi lai.
            lock (_lock)
            {
                PendingRequest pending = new PendingRequest();
                pending.StationName = station.Name;
                pending.Code = code;
                pending.SentAt = DateTime.Now;
                _pending[msg.Id] = pending;
            }

            if (!SendToStation(station, msg))
            {
                // Gui khong duoc thi bo yeu cau khoi danh sach cho.
                lock (_lock)
                {
                    _pending.Remove(msg.Id);
                }
                return false;
            }

            RaiseLog("Da gui yeu cau " + code + " toi " + station.Name + " (id=" + msg.Id + ")");
            return true;
        }

        /// <summary>
        /// Giai doan 4: xu ly RESPONSE hoac ERROR tu may tram.
        /// Ghep cau tra loi voi yeu cau da gui qua truong "id", tinh thoi gian phan hoi
        /// roi bao cho giao dien hien thi.
        /// </summary>
        private void HandleAnswer(StationInfo station, string remoteIp, LanMessage msg, bool isError)
        {
            string name = station != null ? station.Name : remoteIp;
            PendingRequest pending = null;

            lock (_lock)
            {
                if (_pending.TryGetValue(msg.Id, out pending))
                {
                    _pending.Remove(msg.Id);
                }

                if (station != null)
                {
                    station.LastSeen = DateTime.Now;
                }
            }

            RequestAnswer answer = new RequestAnswer();
            answer.StationName = name;
            answer.Payload = msg.Payload;
            answer.IsError = isError;

            if (pending != null)
            {
                answer.Code = pending.Code;
                answer.ElapsedMs = (int)(DateTime.Now - pending.SentAt).TotalMilliseconds;
            }
            else
            {
                // Khong co yeu cau nao dang cho voi id nay: yeu cau da het thoi gian cho truoc do
                // (may tram tra loi muon), hoac da bi bo (may tram ngat ket noi), hoac day la
                // thong diep cua mot chuong trinh khac. Phai bao la THAT BAI chu khong duoc
                // hien nhu mot cau tra loi binh thuong, neu khong se trong nhu may tram
                // tra loi sau 0 ms va nguoi quan tri tuong yeu cau do thanh cong.
                answer.Code = "(khong ro)";
                answer.ElapsedMs = 0;
                answer.IsError = true;
                answer.Payload = "Khong co yeu cau nao dang cho voi id " + msg.Id
                                 + " (co the da het thoi gian cho truoc do).";
            }

            // Tra loi cho yeu cau cua may tram khac la chuyen khong nen xay ra
            // (id la chuoi ngau nhien) -> ghi log de biet ma kiem tra.
            if (pending != null && pending.StationName != name)
            {
                RaiseLog("CANH BAO: " + name + " tra loi yeu cau " + pending.Code
                         + " von da gui cho " + pending.StationName + ".");
            }

            if (isError)
            {
                RaiseLog("May tram " + name + " bao loi cho yeu cau " + answer.Code + ": " + msg.Payload);
            }
            else if (pending == null)
            {
                // Tra loi ma Server khong con yeu cau nao dang cho: ghi log la canh bao
                // chu khong ghi nhu mot cau tra loi binh thuong (xem phan xu ly o tren).
                RaiseLog("CANH BAO: " + name + " tra loi mot yeu cau khong ro (id=" + msg.Id
                         + "): " + msg.Payload);
            }
            else
            {
                RaiseLog("May tram " + name + " da tra loi yeu cau " + answer.Code
                         + " sau " + answer.ElapsedMs + " ms.");
            }

            RaiseAnswerReceived(answer);
        }

        /// <summary>
        /// Cho truoc cac yeu cau cua mot may tram la loi khi may tram do ngat ket noi
        /// (giai doan 4): khong con ket noi thi khong the co cau tra loi, cho them cung vo ich.
        /// </summary>
        private void FailPendingRequestsOf(string stationName, string reason)
        {
            FailPendingRequests(
                delegate(KeyValuePair<string, PendingRequest> item)
                {
                    return item.Value.StationName == stationName;
                },
                reason);
        }

        /// <summary>
        /// Bo tat ca cac yeu cau dang cho tra loi (dung khi Server dung han).
        /// </summary>
        private void FailAllPendingRequests(string reason)
        {
            FailPendingRequests(delegate(KeyValuePair<string, PendingRequest> item) { return true; }, reason);
        }

        /// <summary>
        /// Bo cac yeu cau dang cho tra loi ma thoa dieu kien shouldFail, dong thoi bao cho
        /// giao dien biet tung yeu cau do that bai (khoa co the la ten may tram, hoac tat ca).
        /// </summary>
        private void FailPendingRequests(Func<KeyValuePair<string, PendingRequest>, bool> shouldFail, string reason)
        {
            List<RequestAnswer> failed = new List<RequestAnswer>();
            DateTime now = DateTime.Now;

            lock (_lock)
            {
                List<string> done = new List<string>();

                foreach (KeyValuePair<string, PendingRequest> item in _pending)
                {
                    if (shouldFail(item))
                    {
                        done.Add(item.Key);

                        RequestAnswer answer = new RequestAnswer();
                        answer.StationName = item.Value.StationName;
                        answer.Code = item.Value.Code;
                        answer.Payload = reason;
                        answer.IsError = true;
                        answer.ElapsedMs = (int)(now - item.Value.SentAt).TotalMilliseconds;
                        failed.Add(answer);
                    }
                }

                foreach (string id in done)
                {
                    _pending.Remove(id);
                }
            }

            foreach (RequestAnswer answer in failed)
            {
                RaiseLog("Yeu cau " + answer.Code + " toi " + answer.StationName + " bi bo: " + reason);
                RaiseAnswerReceived(answer);
            }
        }

        /// <summary>Vong lap dinh ky kiem tra may tram nao da qua han (giai doan 2).</summary>
        private void TimeoutLoop(int runId)
        {
            while (_running && runId == _runId)
            {
                Thread.Sleep(Protocol.TimeoutCheckIntervalMs);

                if (!_running || runId != _runId)
                {
                    break;
                }

                CheckTimeouts();
                CheckRequestTimeouts();
            }
        }

        /// <summary>
        /// Giai doan 4: yeu cau nao da gui qua lau ma chua co tra loi thi coi nhu
        /// may tram khong tra loi, bao cho giao dien biet.
        /// </summary>
        private void CheckRequestTimeouts()
        {
            List<RequestAnswer> timedOut = new List<RequestAnswer>();
            DateTime now = DateTime.Now;

            lock (_lock)
            {
                List<string> done = new List<string>();

                foreach (KeyValuePair<string, PendingRequest> item in _pending)
                {
                    PendingRequest pending = item.Value;

                    if ((now - pending.SentAt).TotalMilliseconds > Protocol.RequestTimeoutMs)
                    {
                        done.Add(item.Key);

                        RequestAnswer answer = new RequestAnswer();
                        answer.StationName = pending.StationName;
                        answer.Code = pending.Code;
                        answer.Payload = "May tram khong tra loi trong "
                                         + (Protocol.RequestTimeoutMs / 1000) + " giay.";
                        answer.IsError = true;
                        answer.ElapsedMs = (int)(now - pending.SentAt).TotalMilliseconds;
                        timedOut.Add(answer);
                    }
                }

                foreach (string id in done)
                {
                    _pending.Remove(id);
                }
            }

            // Bao cho giao dien (lam ngoai khoa cho an toan).
            foreach (RequestAnswer answer in timedOut)
            {
                RaiseLog("May tram " + answer.StationName + " khong tra loi yeu cau "
                         + answer.Code + " trong " + (Protocol.RequestTimeoutMs / 1000) + " giay.");
                RaiseAnswerReceived(answer);
            }
        }

        /// <summary>
        /// Duyet danh sach: may tram nao dang Online ma qua 15 giay khong gui thong diep
        /// thi chuyen sang Offline.
        /// </summary>
        private void CheckTimeouts()
        {
            List<StationInfo> justOffline = new List<StationInfo>();
            DateTime now = DateTime.Now;

            lock (_lock)
            {
                foreach (StationInfo station in _stations.Values)
                {
                    if (station.Status == "Online"
                        && (now - station.LastSeen).TotalMilliseconds > Protocol.OfflineTimeoutMs)
                    {
                        station.Status = "Offline";
                        justOffline.Add(station);
                    }
                }
            }

            foreach (StationInfo station in justOffline)
            {
                RaiseLog("May tram " + station.Name + " khong lien lac qua "
                         + (Protocol.OfflineTimeoutMs / 1000) + " giay -> chuyen sang Offline.");
            }

            if (justOffline.Count > 0)
            {
                RaiseStationsChanged();
            }
        }

        /// <summary>Gui mot thong diep toi mot may tram.</summary>
        public bool SendToStation(StationInfo station, LanMessage msg)
        {
            try
            {
                // Phai khoa khi ghi vi ket noi nay con duoc luong doc du lieu dung
                // de tra ACK (xem StationInfo.WriteLock).
                lock (station.WriteLock)
                {
                    station.Writer.WriteLine(msg.ToJson());
                }

                return true;
            }
            catch (Exception ex)
            {
                RaiseLog("Loi gui thong diep toi " + station.Name + ": " + ex.Message);
                return false;
            }
        }

        /// <summary>
        /// Giai doan 3: gui mot thong bao (NOTIFY) toi dung mot may tram.
        /// Day la thong bao rieng, cac may tram khac khong nhan duoc.
        /// </summary>
        public bool SendNotify(StationInfo station, string text)
        {
            LanMessage msg = LanMessage.Create(MessageType.Notify, Protocol.ServerName, text);

            bool ok = SendToStation(station, msg);

            if (ok)
            {
                RaiseLog("Da gui NOTIFY toi " + station.Name + " (id=" + msg.Id + ": " + text + ")");
            }

            return ok;
        }

        /// <summary>
        /// Giai doan 3: gui cung mot thong bao (NOTIFY) cho tat ca may tram dang Online.
        /// Tra ve so may tram da gui duoc.
        /// </summary>
        public int BroadcastNotify(string text)
        {
            List<StationInfo> stations = GetStations();
            int sent = 0;

            foreach (StationInfo station in stations)
            {
                // Chi gui cho may tram dang Online, may Offline thi khong con ket noi de gui.
                if (station.Status != "Online")
                {
                    continue;
                }

                if (SendNotify(station, text))
                {
                    sent++;
                }
            }

            RaiseLog("Da gui NOTIFY cho " + sent + " may tram dang Online.");

            return sent;
        }

        /// <summary>Danh dau may tram la Offline khi ket noi bi ngat.</summary>
        private void MarkOffline(StationInfo station, string remoteIp)
        {
            if (station == null)
            {
                // Ket noi dong truoc khi kip REGISTER.
                RaiseLog("Ket noi tu " + remoteIp + " da dong.");
                return;
            }

            bool changed = false;
            bool isCurrent = false;

            lock (_lock)
            {
                // Ket noi nay co the da bi ket noi moi cua CUNG may tram thay the: may tram
                // ngat roi ket noi lai (hoac doi IP) trong khi Server dang cho no tra loi.
                // Khi do khong duoc danh dau may tram la Offline va cung khong duoc bo cac
                // yeu cau dang cho, vi may tram van dang lien lac qua ket noi moi.
                StationInfo current;
                isCurrent = _stations.TryGetValue(station.Name, out current)
                            && ReferenceEquals(current, station);

                if (isCurrent && station.Status != "Offline")
                {
                    station.Status = "Offline";
                    changed = true;
                }
                // Khong doi LastSeen: no la thoi diem lien lac cuoi cung, khong phai thoi diem ngat.
            }

            if (!isCurrent)
            {
                RaiseLog("Ket noi cu cua may tram " + station.Name + " (" + station.Ip
                         + ") da dong, da co ket noi moi thay the.");
                return;
            }

            RaiseLog("May tram " + station.Name + " (" + station.Ip + ") da ngat ket noi.");

            if (changed)
            {
                RaiseStationsChanged();
            }

            // Giai doan 4: may tram da mat ket noi thi cac yeu cau dang cho no tra loi
            // coi nhu that bai luon, khong cho het thoi gian cho nua.
            FailPendingRequestsOf(station.Name, "May tram da ngat ket noi truoc khi tra loi.");
        }

        // --- Cac ham phat su kien cho giao dien ---

        private void RaiseLog(string text)
        {
            Action<string> handler = Log;
            if (handler != null)
            {
                handler(text);
            }
        }

        private void RaiseStationsChanged()
        {
            Action handler = StationsChanged;
            if (handler != null)
            {
                handler();
            }
        }

        private void RaiseAnswerReceived(RequestAnswer answer)
        {
            Action<RequestAnswer> handler = AnswerReceived;
            if (handler != null)
            {
                handler(answer);
            }
        }
    }
}
