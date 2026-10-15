using Common;

namespace Client
{
    /// <summary>
    /// Giao dien chinh cua Client (may tram): ket noi toi Server, gui REGISTER,
    /// gui HEARTBEAT dinh ky (giai doan 2) va hien thi thong bao NOTIFY nhan duoc
    /// tu Server (giai doan 3).
    /// </summary>
    public partial class MainForm : Form
    {
        // Doi tuong Client TCP (khong lien quan gi den giao dien).
        private readonly MonitorClient _client = new MonitorClient();

        public MainForm()
        {
            InitializeComponent();

            // Dang ky nhan su kien tu Client.
            _client.Log += OnClientLog;
            _client.MessageReceived += OnMessageReceived;
            _client.Disconnected += OnDisconnected;

            numPort.Value = Protocol.Port;

            // Lay ten may lam ten mac dinh cho may tram.
            txtName.Text = Environment.MachineName;

            AppendLog("Chuong trinh Client da khoi dong.");
            AppendLog("Nhap dia chi IP cua Server roi bam 'Ket noi Server'.");
        }

        /// <summary>Bam nut Ket noi: ket noi toi Server va gui REGISTER.</summary>
        private void btnConnect_Click(object sender, EventArgs e)
        {
            if (_client.IsConnected)
            {
                return;
            }

            string host = txtHost.Text.Trim();
            string stationName = txtName.Text.Trim();

            if (host == "")
            {
                MessageBox.Show("Hay nhap dia chi IP cua Server.", "Thieu thong tin",
                    MessageBoxButtons.OK, MessageBoxIcon.Warning);
                return;
            }

            if (stationName == "")
            {
                MessageBox.Show("Hay nhap ten may tram.", "Thieu thong tin",
                    MessageBoxButtons.OK, MessageBoxIcon.Warning);
                return;
            }

            try
            {
                btnConnect.Enabled = false;

                // Neu Server chua chay hoac sai IP thi ham nay nem loi.
                _client.Connect(host, (int)numPort.Value, stationName);

                btnDisconnect.Enabled = true;
                txtHost.Enabled = false;
                numPort.Enabled = false;
                txtName.Enabled = false;
                lblStatus.Text = "Dang ket noi " + host + ":" + numPort.Value;
            }
            catch (Exception ex)
            {
                btnConnect.Enabled = true;
                AppendLog("Khong ket noi duoc toi Server: " + ex.Message);
                MessageBox.Show("Khong ket noi duoc toi Server:\r\n" + ex.Message,
                    "Loi ket noi", MessageBoxButtons.OK, MessageBoxIcon.Error);
            }
        }

        /// <summary>Bam nut Ngat ket noi.</summary>
        private void btnDisconnect_Click(object sender, EventArgs e)
        {
            _client.Disconnect();
            SetDisconnectedUi("Da ngat ket noi.");
        }

        /// <summary>Nhan log tu Client (co the goi tu luong khac).</summary>
        private void OnClientLog(string text)
        {
            if (InvokeRequired)
            {
                BeginInvoke(new Action<string>(OnClientLog), text);
                return;
            }

            AppendLog(text);
        }

        /// <summary>Nhan thong diep tu Server.</summary>
        private void OnMessageReceived(LanMessage msg)
        {
            if (InvokeRequired)
            {
                BeginInvoke(new Action<LanMessage>(OnMessageReceived), msg);
                return;
            }

            if (msg.Type == MessageType.Ack)
            {
                // Server da xac nhan dang ky thanh cong.
                AppendLog("Server xac nhan ACK: " + msg.Payload + "  (id=" + msg.Id + ")");
                lblStatus.Text = "Da dang ky voi Server (Online).";
            }
            else if (msg.Type == MessageType.Notify)
            {
                // Giai doan 3: thong bao rieng ma Server gui cho may tram nay.
                ShowNotify(msg);
            }
            else if (msg.Type == MessageType.Request)
            {
                // Giai doan 4: Server yeu cau may tram nay lam gi do.
                HandleRequest(msg);
            }
            else
            {
                AppendLog("Nhan " + msg.Type + " tu " + msg.From + ": " + msg.Payload);
            }
        }

        /// <summary>
        /// Hien thi thong bao NOTIFY nhan duoc tu Server (giai doan 3):
        /// ghi vao nhat ky, gui ACK xac nhan da nhan, roi hien hop thoai cho nguoi dung thay.
        /// </summary>
        private void ShowNotify(LanMessage msg)
        {
            AppendLog("*** THONG BAO TU SERVER: " + msg.Payload + "  (id=" + msg.Id + ")");
            lblStatus.Text = "Vua nhan thong bao luc " + DateTime.Now.ToString("HH:mm:ss") + ".";

            // Tra ACK ngay de Server biet thong bao da den noi.
            // Ban ACK giu nguyen truong "id" cua NOTIFY nen Server doi chieu duoc.
            _client.SendAck(msg);

            // Hop thoai de nguoi ngoi may tram chac chan nhin thay thong bao.
            MessageBox.Show(msg.Payload, "Thong bao tu Server (" + msg.From + ")",
                MessageBoxButtons.OK, MessageBoxIcon.Information);
        }

        /// <summary>
        /// Giai doan 4: xu ly yeu cau (REQUEST) cua Server.
        /// May tram thu thap thong tin roi tra loi bang RESPONSE.
        /// Neu yeu cau chua duoc ho tro, hoac gap loi khi thu thap thong tin,
        /// thi tra ERROR de Server biet ngay ly do thay vi phai cho het thoi gian.
        /// </summary>
        private void HandleRequest(LanMessage msg)
        {
            AppendLog("*** SERVER YEU CAU: " + msg.Payload + "  (id=" + msg.Id + ")");

            if (msg.Payload == Protocol.RequestStationInfo)
            {
                try
                {
                    string report = StationReport.Build();

                    _client.SendResponse(msg, report);

                    AppendLog("Da tra loi yeu cau " + msg.Payload + ".");
                    lblStatus.Text = "Vua tra loi yeu cau cua Server luc "
                                     + DateTime.Now.ToString("HH:mm:ss") + ".";
                }
                catch (Exception ex)
                {
                    // Khong thu thap duoc thong tin -> bao loi kem ly do cho Server.
                    _client.SendError(msg, "Khong doc duoc thong tin may: " + ex.Message);
                    AppendLog("Loi khi tra loi yeu cau: " + ex.Message);
                }
            }
            else
            {
                _client.SendError(msg, "Khong ho tro yeu cau " + msg.Payload);
                AppendLog("Nhan yeu cau chua duoc ho tro: " + msg.Payload);
            }
        }

        /// <summary>Server ngat ket noi (hoac duong truyen bi dut).</summary>
        private void OnDisconnected()
        {
            if (InvokeRequired)
            {
                BeginInvoke(new Action(OnDisconnected));
                return;
            }

            AppendLog("Da mat ket noi toi Server.");
            SetDisconnectedUi("Mat ket noi toi Server.");
        }

        /// <summary>Tra giao dien ve trang thai chua ket noi.</summary>
        private void SetDisconnectedUi(string statusText)
        {
            btnConnect.Enabled = true;
            btnDisconnect.Enabled = false;
            txtHost.Enabled = true;
            numPort.Enabled = true;
            txtName.Enabled = true;
            lblStatus.Text = statusText;
        }

        /// <summary>Ghi them mot dong vao o thong bao.</summary>
        private void AppendLog(string text)
        {
            txtLog.AppendText("[" + DateTime.Now.ToString("HH:mm:ss") + "] " + text + "\r\n");
        }
    }
}
