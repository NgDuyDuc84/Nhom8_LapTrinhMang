using System.Text;
using Common;

namespace Server
{
    /// <summary>
    /// Giao dien chinh cua Server: bat/dung lang nghe, hien danh sach may tram
    /// (ten, IP, trang thai, lan lien lac cuoi), gui thong bao NOTIFY toi may tram
    /// dang chon trong bang (giai doan 3), gui yeu cau REQUEST va hien ket qua
    /// tra loi cua may tram (giai doan 4), va ghi log.
    /// </summary>
    public partial class MainForm : Form
    {
        // Doi tuong Server TCP (khong lien quan gi den giao dien).
        private readonly MonitorServer _server = new MonitorServer();

        public MainForm()
        {
            InitializeComponent();

            // Dang ky nhan su kien tu Server.
            _server.Log += OnServerLog;
            _server.StationsChanged += OnStationsChanged;
            _server.AnswerReceived += OnAnswerReceived;

            numPort.Value = Protocol.Port;

            AppendLog("Chuong trinh Server da khoi dong.");
            AppendLog("Bam 'Bat dau lang nghe' de cho cac may tram ket noi toi.");
        }

        /// <summary>Bam nut Bat dau.</summary>
        private void btnStart_Click(object sender, EventArgs e)
        {
            try
            {
                _server.Start((int)numPort.Value);

                btnStart.Enabled = false;
                btnStop.Enabled = true;
                numPort.Enabled = false;
                lblStatus.Text = "Dang lang nghe tren cong " + numPort.Value;
            }
            catch (Exception ex)
            {
                // Thuong gap khi cong dang bi chuong trinh khac chiem.
                AppendLog("Loi khoi dong Server: " + ex.Message);
                MessageBox.Show("Khong khoi dong duoc Server:\r\n" + ex.Message,
                    "Loi", MessageBoxButtons.OK, MessageBoxIcon.Error);
            }
        }

        /// <summary>Bam nut Dung.</summary>
        private void btnStop_Click(object sender, EventArgs e)
        {
            _server.Stop();

            btnStart.Enabled = true;
            btnStop.Enabled = false;
            numPort.Enabled = true;
            lblStatus.Text = "Da dung";
        }

        /// <summary>Nguoi dung chon mot dong khac trong bang -> cap nhat may tram nhan thong bao.</summary>
        private void dgvStations_SelectionChanged(object sender, EventArgs e)
        {
            UpdateSendTarget();
        }

        /// <summary>
        /// Cap nhat dong chu "May tram nhan" theo dong dang chon trong bang.
        /// Chua chon dong nao thi khong cho bam nut gui.
        /// </summary>
        private void UpdateSendTarget()
        {
            StationInfo station = GetSelectedStation();

            if (station == null)
            {
                lblSendTo.Text = "May tram nhan: (chua chon may nao)";
                btnSendSelected.Enabled = false;
                btnRequestInfo.Enabled = false;
            }
            else
            {
                lblSendTo.Text = "May tram nhan: " + station.Name
                                 + "  (" + station.Ip + " - " + station.Status + ")";
                btnSendSelected.Enabled = true;
                btnRequestInfo.Enabled = true;
            }
        }

        /// <summary>Lay may tram dang duoc chon trong bang. Tra ve null neu chua chon dong nao.</summary>
        private StationInfo GetSelectedStation()
        {
            if (dgvStations.SelectedRows.Count == 0)
            {
                return null;
            }

            string name = dgvStations.SelectedRows[0].Cells["colName"].Value as string;
            if (name == null)
            {
                return null;
            }

            // Lay lai doi tuong may tram tu Server theo ten hien tren bang.
            foreach (StationInfo station in _server.GetStations())
            {
                if (station.Name == name)
                {
                    return station;
                }
            }

            return null;
        }

        /// <summary>
        /// Giai doan 3: gui thong bao NOTIFY toi may tram dang chon trong bang.
        /// Chi may tram nay nhan duoc, cac may tram khac khong bi anh huong.
        /// </summary>
        private void btnSendSelected_Click(object sender, EventArgs e)
        {
            StationInfo station = GetSelectedStation();

            if (station == null)
            {
                MessageBox.Show("Hay chon mot may tram trong bang truoc.", "Chua chon may tram",
                    MessageBoxButtons.OK, MessageBoxIcon.Warning);
                return;
            }

            string text = txtMessage.Text.Trim();
            if (text == "")
            {
                MessageBox.Show("Hay nhap noi dung thong bao.", "Thieu noi dung",
                    MessageBoxButtons.OK, MessageBoxIcon.Warning);
                txtMessage.Focus();
                return;
            }

            // May tram Offline thi khong con ket noi nao de gui -> hoi lai truoc.
            if (station.Status != "Online")
            {
                DialogResult answer = MessageBox.Show(
                    "May tram " + station.Name + " dang Offline nen thong bao se khong den duoc.\r\nVan gui?",
                    "May tram dang Offline", MessageBoxButtons.YesNo, MessageBoxIcon.Warning);

                if (answer != DialogResult.Yes)
                {
                    return;
                }
            }

            // Ket qua gui da duoc Server ghi ra log nen o day khong ghi lai nua.
            if (_server.SendNotify(station, text))
            {
                txtMessage.Clear();
            }
        }

        /// <summary>
        /// Giai doan 3: gui cung mot thong bao cho tat ca may tram dang Online.
        /// </summary>
        private void btnSendAll_Click(object sender, EventArgs e)
        {
            string text = txtMessage.Text.Trim();

            if (text == "")
            {
                MessageBox.Show("Hay nhap noi dung thong bao.", "Thieu noi dung",
                    MessageBoxButtons.OK, MessageBoxIcon.Warning);
                txtMessage.Focus();
                return;
            }

            int online = 0;
            foreach (StationInfo station in _server.GetStations())
            {
                if (station.Status == "Online")
                {
                    online++;
                }
            }

            if (online == 0)
            {
                MessageBox.Show("Chua co may tram nao dang Online de gui.", "Khong gui duoc",
                    MessageBoxButtons.OK, MessageBoxIcon.Warning);
                return;
            }

            if (_server.BroadcastNotify(text) > 0)
            {
                txtMessage.Clear();
            }
        }

        /// <summary>
        /// Giai doan 4: gui yeu cau lay thong tin may tinh cua may tram dang chon trong bang.
        /// </summary>
        private void btnRequestInfo_Click(object sender, EventArgs e)
        {
            StationInfo station = GetSelectedStation();

            if (station == null)
            {
                MessageBox.Show("Hay chon mot may tram trong bang truoc.", "Chua chon may tram",
                    MessageBoxButtons.OK, MessageBoxIcon.Warning);
                return;
            }

            // May tram Offline thi khong con ket noi nao de gui -> bao luon, khong gui.
            if (station.Status != "Online")
            {
                MessageBox.Show("May tram " + station.Name + " dang Offline nen khong gui duoc yeu cau.",
                    "May tram dang Offline", MessageBoxButtons.OK, MessageBoxIcon.Warning);
                return;
            }

            // Ket qua se den sau (qua su kien AnswerReceived) nen o day khong hien gi them.
            _server.SendRequest(station, Protocol.RequestStationInfo);
        }

        /// <summary>
        /// Giai doan 4: hien ket qua tra loi cua may tram (co the goi tu luong khac).
        /// Gom ca truong hop loi: may tram bao loi, khong tra loi, hoac da ngat ket noi.
        /// </summary>
        private void OnAnswerReceived(RequestAnswer answer)
        {
            if (InvokeRequired)
            {
                BeginInvoke(new Action<RequestAnswer>(OnAnswerReceived), answer);
                return;
            }

            StringBuilder text = new StringBuilder();

            text.Append("[" + DateTime.Now.ToString("HH:mm:ss") + "] " + answer.StationName
                        + " - yeu cau " + answer.Code
                        + (answer.IsError ? " THAT BAI" : " tra loi sau " + answer.ElapsedMs + " ms")
                        + "\r\n");

            if (answer.IsError)
            {
                text.Append("    " + answer.Payload + "\r\n");
            }
            else
            {
                // Noi dung tra ve co dang "khoa=gia tri; khoa=gia tri; ..."
                // -> tach ra moi truong mot dong cho de doc.
                string[] fields = answer.Payload.Split(new string[] { Protocol.FieldSeparator },
                                                       StringSplitOptions.RemoveEmptyEntries);

                foreach (string field in fields)
                {
                    int split = field.IndexOf('=');

                    if (split > 0)
                    {
                        text.Append("    " + field.Substring(0, split).Trim()
                                    + ": " + field.Substring(split + 1).Trim() + "\r\n");
                    }
                    else
                    {
                        text.Append("    " + field.Trim() + "\r\n");
                    }
                }
            }

            txtAnswer.AppendText(text.ToString());
            txtAnswer.SelectionStart = txtAnswer.TextLength;   // dua con tro xuong cuoi
            txtAnswer.ScrollToCaret();
        }

        /// <summary>Nhan thong bao log tu Server (co the goi tu luong khac).</summary>
        private void OnServerLog(string text)
        {
            // Su kien nay den tu luong mang, phai chuyen sang luong giao dien moi sua duoc TextBox.
            if (InvokeRequired)
            {
                BeginInvoke(new Action<string>(OnServerLog), text);
                return;
            }

            AppendLog(text);
        }

        /// <summary>Danh sach may tram co thay doi -> ve lai bang.</summary>
        private void OnStationsChanged()
        {
            if (InvokeRequired)
            {
                BeginInvoke(new Action(OnStationsChanged));
                return;
            }

            RefreshStationList();
        }

        /// <summary>
        /// Cap nhat bang danh sach may tram.
        /// Chi sua dung nhung dong co thay doi, khong xoa het roi ve lai.
        /// Lam vay de bang khong bi giat man hinh va khong mat dong dang chon
        /// (vi giai doan 2 cu 5 giay lai co 1 lan cap nhat vi HEARTBEAT).
        /// </summary>
        private void RefreshStationList()
        {
            List<StationInfo> stations = _server.GetStations();

            // Buoc 1: xoa nhung dong khong con may tram tuong ung.
            for (int i = dgvStations.Rows.Count - 1; i >= 0; i--)
            {
                string rowName = dgvStations.Rows[i].Cells["colName"].Value as string;

                bool stillExists = false;
                foreach (StationInfo station in stations)
                {
                    if (station.Name == rowName)
                    {
                        stillExists = true;
                        break;
                    }
                }

                if (!stillExists)
                {
                    dgvStations.Rows.RemoveAt(i);
                }
            }

            // Buoc 2: them dong moi hoac cap nhat dong da co.
            foreach (StationInfo station in stations)
            {
                DataGridViewRow row = FindStationRow(station.Name);

                if (row == null)
                {
                    dgvStations.Rows.Add(station.Name, station.Ip, station.Status, FormatLastSeen(station.LastSeen));
                }
                else
                {
                    row.Cells["colIp"].Value = station.Ip;
                    row.Cells["colStatus"].Value = station.Status;
                    row.Cells["colLastSeen"].Value = FormatLastSeen(station.LastSeen);
                }
            }

            // Trang thai cua may tram dang chon co the vua doi (Online <-> Offline)
            // nen cap nhat lai dong chu "May tram nhan" cho khop voi bang.
            UpdateSendTarget();
        }

        /// <summary>Tim dong trong bang theo ten may tram. Tra ve null neu chua co dong nao.</summary>
        private DataGridViewRow FindStationRow(string stationName)
        {
            foreach (DataGridViewRow row in dgvStations.Rows)
            {
                if ((row.Cells["colName"].Value as string) == stationName)
                {
                    return row;
                }
            }

            return null;
        }

        /// <summary>Dinh dang thoi diem lien lac cuoi de hien len bang.</summary>
        private string FormatLastSeen(DateTime lastSeen)
        {
            return lastSeen.ToString("HH:mm:ss dd/MM/yyyy");
        }

        /// <summary>Ghi them mot dong vao o log.</summary>
        private void AppendLog(string text)
        {
            txtLog.AppendText("[" + DateTime.Now.ToString("HH:mm:ss") + "] " + text + "\r\n");
        }
    }
}
