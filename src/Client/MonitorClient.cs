using System.Net;
using System.Net.Sockets;
using System.Text;
using System.Text.Json;
using Common;

namespace Client
{
    /// <summary>
    /// Client TCP: ket noi toi Server, gui va nhan thong diep JSON theo tung dong.
    /// Giai doan 2: sau khi ket noi, Client con gui HEARTBEAT dinh ky moi 5 giay
    /// de Server biet may tram nay con dang hoat dong.
    /// Giai doan 3: Client nhan thong bao NOTIFY tu Server va gui ACK xac nhan da nhan.
    /// Giai doan 4: Client nhan REQUEST tu Server roi tra loi bang RESPONSE (hoac ERROR).
    /// </summary>
    public class MonitorClient
    {
        private TcpClient _client;
        private StreamWriter _writer;
        private Thread _receiveThread;
        private Thread _heartbeatThread;
        private bool _connected;

        // Moi lan Connect() tang so nay len 1. Cac luong cua ket noi cu (doc du lieu,
        // gui nhip tim) so sanh so da luu voi so hien tai de biet minh da bi ket noi moi
        // thay the chua. Neu khong co so nay thi khi nguoi dung ngat roi ket noi lai,
        // luong doc du lieu cua ket noi cu thuc day se thay _connected dang la true
        // (cua ket noi moi) va bao "mat ket noi", lam hong luon ket noi moi.
        private int _connectionId;

        // Giai doan 2 va 3 lam cho Client ghi xuong ket noi tu hai luong khac nhau
        // (luong HEARTBEAT, luong giao dien khi tra ACK). Hai luong cung goi WriteLine
        // thi hai dong JSON se bi xen vao nhau, nen phai khoa lai khi ghi.
        private readonly object _sendLock = new object();

        // Ten may tram nay, dung lam truong "from" cua thong diep HEARTBEAT.
        private string _stationName = "";

        // Su kien bao cho giao dien biet co chuyen xay ra.
        public event Action<string> Log;
        public event Action<LanMessage> MessageReceived;
        public event Action Disconnected;

        /// <summary>Dang ket noi toi Server hay khong.</summary>
        public bool IsConnected
        {
            get { return _connected; }
        }

        /// <summary>
        /// Ket noi toi Server, gui ngay thong diep REGISTER roi bat dau gui HEARTBEAT.
        /// Nem loi neu khong ket noi duoc (sai IP, Server chua chay, ...).
        /// </summary>
        public void Connect(string host, int port, string stationName)
        {
            _stationName = stationName;

            _client = new TcpClient();

            try
            {
                _client.Connect(host, port);
            }
            catch (Exception)
            {
                // Ket noi that bai (sai IP, Server chua chay): dong lai ngay de khong
                // ro ri socket moi lan nguoi dung bam nham dia chi.
                _client.Close();
                throw;
            }

            _connected = true;

            // Danh dau day la ket noi hien tai. Cac luong cua ket noi truoc (neu con)
            // se thay so khac nen tu thoat.
            int connectionId = ++_connectionId;

            NetworkStream stream = _client.GetStream();

            // Doc va ghi theo tung dong cho dung dinh dang giao thuc.
            StreamReader reader = new StreamReader(stream, Encoding.UTF8, false);

            _writer = new StreamWriter(stream, new UTF8Encoding(false));
            _writer.AutoFlush = true;
            _writer.NewLine = Protocol.LineEnd;

            // Mot luong rieng chi de lien tuc doc thong diep tu Server.
            _receiveThread = new Thread(() => ReceiveLoop(reader, connectionId));
            _receiveThread.IsBackground = true;
            _receiveThread.Start();

            // Giai doan 2: mot luong rieng gui HEARTBEAT dinh ky.
            _heartbeatThread = new Thread(() => HeartbeatLoop(connectionId));
            _heartbeatThread.IsBackground = true;
            _heartbeatThread.Start();

            RaiseLog("Da ket noi toi Server " + host + ":" + port);

            // Gui REGISTER: ten may o truong "from", dia chi IP o truong "payload".
            LanMessage register = LanMessage.Create(MessageType.Register, stationName, GetLocalIp());
            Send(register);
        }

        /// <summary>Ngat ket noi toi Server (do nguoi dung bam nut).</summary>
        public void Disconnect()
        {
            // Dat co truoc khi dong de cac luong dang chay tu thoat.
            _connected = false;

            try
            {
                if (_client != null)
                {
                    _client.Close();
                }
            }
            catch (Exception)
            {
            }

            RaiseLog("Da ngat ket noi toi Server.");
        }

        /// <summary>Gui mot thong diep JSON xuong Server.</summary>
        public void Send(LanMessage msg)
        {
            try
            {
                lock (_sendLock)
                {
                    _writer.WriteLine(msg.ToJson());
                }

                RaiseLog("Da gui " + msg.Type + " toi Server.");
            }
            catch (Exception ex)
            {
                RaiseLog("Loi gui thong diep: " + ex.Message);
            }
        }

        /// <summary>
        /// Giai doan 4: tra loi mot yeu cau cua Server bang thong diep RESPONSE.
        /// Giu nguyen truong "id" cua REQUEST de Server biet cau tra loi nay
        /// ung voi yeu cau nao.
        /// </summary>
        public void SendResponse(LanMessage request, string payload)
        {
            LanMessage response = LanMessage.Create(MessageType.Response, _stationName, payload);
            response.Id = request.Id;

            Send(response);
        }

        /// <summary>
        /// Giai doan 4: bao cho Server biet yeu cau khong xu ly duoc (chua ho tro,
        /// hoac gap loi khi xu ly). Nho co thong diep nay ma Server khong phai cho
        /// het thoi gian roi moi bao loi.
        /// </summary>
        public void SendError(LanMessage request, string reason)
        {
            LanMessage error = LanMessage.Create(MessageType.Error, _stationName, reason);
            error.Id = request.Id;

            Send(error);
        }

        /// <summary>
        /// Giai doan 3: tra ACK cho mot thong diep vua nhan duoc tu Server.
        /// Ban ACK giu nguyen truong "id" cua thong diep goc de Server doi chieu duoc
        /// no xac nhan cho thong bao nao.
        /// Ham nay duoc goi tu luong giao dien (khi nguoi dung doc thong bao) trong luc
        /// luong HEARTBEAT van dang gui, nen viec ghi phai di qua Send() co khoa.
        /// </summary>
        public void SendAck(LanMessage original)
        {
            LanMessage ack = LanMessage.Create(MessageType.Ack, _stationName, original.Type + "_OK");
            ack.Id = original.Id;

            Send(ack);
        }

        /// <summary>
        /// Cu 5 giay gui mot thong diep HEARTBEAT de bao cho Server biet may tram con song.
        /// vd: {"type":"HEARTBEAT","id":"...","from":"PC01","payload":"","timestamp":"..."}
        /// </summary>
        private void HeartbeatLoop(int connectionId)
        {
            // Luong nay chi duoc song khi no van thuoc ket noi hien tai.
            // (Neu nguoi dung ngat roi ket noi lai, so ket noi da doi nen luong cu
            //  tu thoat, tranh gui trung 2 lan.)
            while (_connected && connectionId == _connectionId)
            {
                Thread.Sleep(Protocol.HeartbeatIntervalMs);

                if (!_connected || connectionId != _connectionId)
                {
                    break;
                }

                LanMessage heartbeat = LanMessage.Create(MessageType.Heartbeat, _stationName, "");
                Send(heartbeat);
            }
        }

        /// <summary>Vong lap doc thong diep tu Server cho den khi mat ket noi.</summary>
        private void ReceiveLoop(StreamReader reader, int connectionId)
        {
            try
            {
                string line;
                while (_connected && connectionId == _connectionId
                       && (line = reader.ReadLine()) != null)
                {
                    LanMessage msg;
                    try
                    {
                        msg = LanMessage.FromJson(line);
                    }
                    catch (JsonException)
                    {
                        RaiseLog("Nhan duoc JSON sai dinh dang: " + line);
                        continue;
                    }

                    RaiseMessageReceived(msg);
                }
            }
            catch (Exception ex)
            {
                // Thuong gap khi Server tat dot ngot.
                if (_connected && connectionId == _connectionId)
                {
                    RaiseLog("Mat ket noi toi Server: " + ex.Message);
                }
            }
            finally
            {
                // Chi bao mat ket noi khi day van la ket noi hien tai: nguoi dung chu dong
                // ngat thi Disconnect() da xu ly roi, con khi da ket noi lai (connectionId cu)
                // thi khong duoc bao gi nua, neu khong se bao nham la ket noi moi bi mat.
                if (_connected && connectionId == _connectionId)
                {
                    _connected = false;
                    RaiseDisconnected();
                }
            }
        }

        /// <summary>Lay dia chi IPv4 cua may nay de gui kem trong REGISTER.</summary>
        private string GetLocalIp()
        {
            try
            {
                IPAddress[] addresses = Dns.GetHostAddresses(Dns.GetHostName());
                foreach (IPAddress ip in addresses)
                {
                    if (ip.AddressFamily == AddressFamily.InterNetwork)
                    {
                        return ip.ToString();
                    }
                }
            }
            catch (Exception)
            {
            }

            return "0.0.0.0";
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

        private void RaiseMessageReceived(LanMessage msg)
        {
            Action<LanMessage> handler = MessageReceived;
            if (handler != null)
            {
                handler(msg);
            }
        }

        private void RaiseDisconnected()
        {
            Action handler = Disconnected;
            if (handler != null)
            {
                handler();
            }
        }
    }
}
