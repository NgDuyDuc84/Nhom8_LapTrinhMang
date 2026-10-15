namespace Server
{
    partial class MainForm
    {
        /// <summary>Thanh phan giao dien (do Windows Forms Designer quan ly).</summary>
        private System.ComponentModel.IContainer components = null;

        /// <summary>Giai phong tai nguyen dang dung.</summary>
        protected override void Dispose(bool disposing)
        {
            if (disposing && (components != null))
            {
                components.Dispose();
            }
            base.Dispose(disposing);
        }

        // Khai bao cac control.
        private System.Windows.Forms.Panel panelTop;
        private System.Windows.Forms.Label lblPort;
        private System.Windows.Forms.NumericUpDown numPort;
        private System.Windows.Forms.Button btnStart;
        private System.Windows.Forms.Button btnStop;
        private System.Windows.Forms.Label lblStatus;
        private System.Windows.Forms.GroupBox groupBoxStations;
        private System.Windows.Forms.DataGridView dgvStations;
        private System.Windows.Forms.GroupBox groupBoxSend;
        private System.Windows.Forms.Label lblSendTo;
        private System.Windows.Forms.Label lblMsg;
        private System.Windows.Forms.TextBox txtMessage;
        private System.Windows.Forms.Button btnSendSelected;
        private System.Windows.Forms.Button btnSendAll;
        private System.Windows.Forms.Button btnRequestInfo;
        private System.Windows.Forms.Label lblAnswer;
        private System.Windows.Forms.TextBox txtAnswer;
        private System.Windows.Forms.GroupBox groupBoxLog;
        private System.Windows.Forms.TextBox txtLog;

        private void InitializeComponent()
        {
            this.panelTop = new System.Windows.Forms.Panel();
            this.lblPort = new System.Windows.Forms.Label();
            this.numPort = new System.Windows.Forms.NumericUpDown();
            this.btnStart = new System.Windows.Forms.Button();
            this.btnStop = new System.Windows.Forms.Button();
            this.lblStatus = new System.Windows.Forms.Label();
            this.groupBoxStations = new System.Windows.Forms.GroupBox();
            this.dgvStations = new System.Windows.Forms.DataGridView();
            this.groupBoxSend = new System.Windows.Forms.GroupBox();
            this.lblSendTo = new System.Windows.Forms.Label();
            this.lblMsg = new System.Windows.Forms.Label();
            this.txtMessage = new System.Windows.Forms.TextBox();
            this.btnSendSelected = new System.Windows.Forms.Button();
            this.btnSendAll = new System.Windows.Forms.Button();
            this.btnRequestInfo = new System.Windows.Forms.Button();
            this.lblAnswer = new System.Windows.Forms.Label();
            this.txtAnswer = new System.Windows.Forms.TextBox();
            this.groupBoxLog = new System.Windows.Forms.GroupBox();
            this.txtLog = new System.Windows.Forms.TextBox();
            this.panelTop.SuspendLayout();
            ((System.ComponentModel.ISupportInitialize)(this.numPort)).BeginInit();
            this.groupBoxStations.SuspendLayout();
            ((System.ComponentModel.ISupportInitialize)(this.dgvStations)).BeginInit();
            this.groupBoxSend.SuspendLayout();
            this.groupBoxLog.SuspendLayout();
            this.SuspendLayout();

            // ---------- panelTop: chua cac dieu khien bat/dung ----------
            this.panelTop.Controls.Add(this.lblStatus);
            this.panelTop.Controls.Add(this.btnStop);
            this.panelTop.Controls.Add(this.btnStart);
            this.panelTop.Controls.Add(this.numPort);
            this.panelTop.Controls.Add(this.lblPort);
            this.panelTop.Dock = System.Windows.Forms.DockStyle.Top;
            this.panelTop.Location = new System.Drawing.Point(0, 0);
            this.panelTop.Name = "panelTop";
            this.panelTop.Size = new System.Drawing.Size(960, 48);
            this.panelTop.TabIndex = 0;

            // lblPort
            this.lblPort.AutoSize = true;
            this.lblPort.Location = new System.Drawing.Point(12, 16);
            this.lblPort.Name = "lblPort";
            this.lblPort.Size = new System.Drawing.Size(48, 15);
            this.lblPort.TabIndex = 0;
            this.lblPort.Text = "Cong:";

            // numPort
            this.numPort.Location = new System.Drawing.Point(66, 13);
            this.numPort.Maximum = new decimal(new int[] { 65535, 0, 0, 0 });
            this.numPort.Minimum = new decimal(new int[] { 1, 0, 0, 0 });
            this.numPort.Name = "numPort";
            this.numPort.Size = new System.Drawing.Size(80, 23);
            this.numPort.TabIndex = 1;
            this.numPort.Value = new decimal(new int[] { 5000, 0, 0, 0 });

            // btnStart
            this.btnStart.Location = new System.Drawing.Point(160, 12);
            this.btnStart.Name = "btnStart";
            this.btnStart.Size = new System.Drawing.Size(150, 26);
            this.btnStart.TabIndex = 2;
            this.btnStart.Text = "&Bat dau lang nghe";
            this.btnStart.UseVisualStyleBackColor = true;
            this.btnStart.Click += new System.EventHandler(this.btnStart_Click);

            // btnStop
            this.btnStop.Enabled = false;
            this.btnStop.Location = new System.Drawing.Point(318, 12);
            this.btnStop.Name = "btnStop";
            this.btnStop.Size = new System.Drawing.Size(80, 26);
            this.btnStop.TabIndex = 3;
            this.btnStop.Text = "D&ung";
            this.btnStop.UseVisualStyleBackColor = true;
            this.btnStop.Click += new System.EventHandler(this.btnStop_Click);

            // lblStatus
            this.lblStatus.AutoSize = true;
            this.lblStatus.Location = new System.Drawing.Point(414, 18);
            this.lblStatus.Name = "lblStatus";
            this.lblStatus.Size = new System.Drawing.Size(70, 15);
            this.lblStatus.TabIndex = 4;
            this.lblStatus.Text = "Chua chay";

            // ---------- groupBoxStations: danh sach may tram ----------
            this.groupBoxStations.Controls.Add(this.dgvStations);
            this.groupBoxStations.Dock = System.Windows.Forms.DockStyle.Top;
            this.groupBoxStations.Location = new System.Drawing.Point(0, 48);
            this.groupBoxStations.Name = "groupBoxStations";
            this.groupBoxStations.Size = new System.Drawing.Size(960, 280);
            this.groupBoxStations.TabIndex = 1;
            this.groupBoxStations.TabStop = false;
            this.groupBoxStations.Text = "Danh sach may tram trong mang LAN";

            // dgvStations
            this.dgvStations.AllowUserToAddRows = false;
            this.dgvStations.AllowUserToDeleteRows = false;
            this.dgvStations.AllowUserToResizeRows = false;
            this.dgvStations.AutoSizeColumnsMode = System.Windows.Forms.DataGridViewAutoSizeColumnsMode.Fill;
            this.dgvStations.ColumnHeadersHeightSizeMode = System.Windows.Forms.DataGridViewColumnHeadersHeightSizeMode.AutoSize;
            this.dgvStations.Dock = System.Windows.Forms.DockStyle.Fill;
            this.dgvStations.Location = new System.Drawing.Point(3, 19);
            this.dgvStations.MultiSelect = false;
            this.dgvStations.Name = "dgvStations";
            this.dgvStations.ReadOnly = true;
            this.dgvStations.RowHeadersVisible = false;
            this.dgvStations.SelectionMode = System.Windows.Forms.DataGridViewSelectionMode.FullRowSelect;
            this.dgvStations.Size = new System.Drawing.Size(954, 258);
            this.dgvStations.TabIndex = 0;
            this.dgvStations.SelectionChanged += new System.EventHandler(this.dgvStations_SelectionChanged);

            // Cac cot cua bang
            System.Windows.Forms.DataGridViewTextBoxColumn colName = new System.Windows.Forms.DataGridViewTextBoxColumn();
            colName.HeaderText = "Ten may";
            colName.Name = "colName";
            colName.ReadOnly = true;
            colName.FillWeight = 25F;

            System.Windows.Forms.DataGridViewTextBoxColumn colIp = new System.Windows.Forms.DataGridViewTextBoxColumn();
            colIp.HeaderText = "Dia chi IP";
            colIp.Name = "colIp";
            colIp.ReadOnly = true;
            colIp.FillWeight = 25F;

            System.Windows.Forms.DataGridViewTextBoxColumn colStatus = new System.Windows.Forms.DataGridViewTextBoxColumn();
            colStatus.HeaderText = "Trang thai";
            colStatus.Name = "colStatus";
            colStatus.ReadOnly = true;
            colStatus.FillWeight = 20F;

            System.Windows.Forms.DataGridViewTextBoxColumn colLastSeen = new System.Windows.Forms.DataGridViewTextBoxColumn();
            colLastSeen.HeaderText = "Lan lien lac cuoi";
            colLastSeen.Name = "colLastSeen";
            colLastSeen.ReadOnly = true;
            colLastSeen.FillWeight = 30F;

            this.dgvStations.Columns.AddRange(new System.Windows.Forms.DataGridViewColumn[] {
                colName, colIp, colStatus, colLastSeen});

            // ---------- groupBoxSend: gui thong bao / yeu cau toi may tram (giai doan 3, 4) ----------
            this.groupBoxSend.Controls.Add(this.txtAnswer);
            this.groupBoxSend.Controls.Add(this.lblAnswer);
            this.groupBoxSend.Controls.Add(this.txtMessage);
            this.groupBoxSend.Controls.Add(this.lblMsg);
            this.groupBoxSend.Controls.Add(this.btnRequestInfo);
            this.groupBoxSend.Controls.Add(this.btnSendAll);
            this.groupBoxSend.Controls.Add(this.btnSendSelected);
            this.groupBoxSend.Controls.Add(this.lblSendTo);
            this.groupBoxSend.Dock = System.Windows.Forms.DockStyle.Top;
            this.groupBoxSend.Location = new System.Drawing.Point(0, 328);
            this.groupBoxSend.Name = "groupBoxSend";
            this.groupBoxSend.Size = new System.Drawing.Size(960, 200);
            this.groupBoxSend.TabIndex = 2;
            this.groupBoxSend.TabStop = false;
            this.groupBoxSend.Text = "Gui thong bao / yeu cau toi may tram";

            // lblSendTo
            this.lblSendTo.AutoSize = true;
            this.lblSendTo.Location = new System.Drawing.Point(12, 25);
            this.lblSendTo.Name = "lblSendTo";
            this.lblSendTo.Size = new System.Drawing.Size(180, 15);
            this.lblSendTo.TabIndex = 0;
            this.lblSendTo.Text = "May tram nhan: (chua chon may nao)";

            // btnSendSelected
            this.btnSendSelected.Enabled = false;
            this.btnSendSelected.Location = new System.Drawing.Point(560, 20);
            this.btnSendSelected.Name = "btnSendSelected";
            this.btnSendSelected.Size = new System.Drawing.Size(120, 28);
            this.btnSendSelected.TabIndex = 1;
            this.btnSendSelected.Text = "&Gui may da chon";
            this.btnSendSelected.UseVisualStyleBackColor = true;
            this.btnSendSelected.Click += new System.EventHandler(this.btnSendSelected_Click);

            // btnSendAll
            this.btnSendAll.Location = new System.Drawing.Point(690, 20);
            this.btnSendAll.Name = "btnSendAll";
            this.btnSendAll.Size = new System.Drawing.Size(90, 28);
            this.btnSendAll.TabIndex = 2;
            this.btnSendAll.Text = "Gui &tat ca";
            this.btnSendAll.UseVisualStyleBackColor = true;
            this.btnSendAll.Click += new System.EventHandler(this.btnSendAll_Click);

            // btnRequestInfo (giai doan 4)
            this.btnRequestInfo.Enabled = false;
            this.btnRequestInfo.Location = new System.Drawing.Point(790, 20);
            this.btnRequestInfo.Name = "btnRequestInfo";
            this.btnRequestInfo.Size = new System.Drawing.Size(150, 28);
            this.btnRequestInfo.TabIndex = 3;
            this.btnRequestInfo.Text = "&Yeu cau thong tin may";
            this.btnRequestInfo.UseVisualStyleBackColor = true;
            this.btnRequestInfo.Click += new System.EventHandler(this.btnRequestInfo_Click);

            // lblMsg
            this.lblMsg.AutoSize = true;
            this.lblMsg.Location = new System.Drawing.Point(12, 58);
            this.lblMsg.Name = "lblMsg";
            this.lblMsg.Size = new System.Drawing.Size(120, 15);
            this.lblMsg.TabIndex = 4;
            this.lblMsg.Text = "Noi dung thong bao:";

            // txtMessage
            this.txtMessage.Location = new System.Drawing.Point(150, 55);
            this.txtMessage.Name = "txtMessage";
            this.txtMessage.Size = new System.Drawing.Size(790, 23);
            this.txtMessage.TabIndex = 5;

            // lblAnswer
            this.lblAnswer.AutoSize = true;
            this.lblAnswer.Location = new System.Drawing.Point(12, 92);
            this.lblAnswer.Name = "lblAnswer";
            this.lblAnswer.Size = new System.Drawing.Size(200, 15);
            this.lblAnswer.TabIndex = 6;
            this.lblAnswer.Text = "Ket qua tra loi tu may tram:";

            // txtAnswer
            this.txtAnswer.BackColor = System.Drawing.SystemColors.Window;
            this.txtAnswer.Font = new System.Drawing.Font("Consolas", 9F);
            this.txtAnswer.Location = new System.Drawing.Point(12, 112);
            this.txtAnswer.Multiline = true;
            this.txtAnswer.Name = "txtAnswer";
            this.txtAnswer.ReadOnly = true;
            this.txtAnswer.ScrollBars = System.Windows.Forms.ScrollBars.Vertical;
            this.txtAnswer.Size = new System.Drawing.Size(928, 78);
            this.txtAnswer.TabIndex = 7;

            // ---------- groupBoxLog: nhat ky su kien ----------
            this.groupBoxLog.Controls.Add(this.txtLog);
            this.groupBoxLog.Dock = System.Windows.Forms.DockStyle.Fill;
            this.groupBoxLog.Location = new System.Drawing.Point(0, 528);
            this.groupBoxLog.Name = "groupBoxLog";
            this.groupBoxLog.Size = new System.Drawing.Size(960, 232);
            this.groupBoxLog.TabIndex = 3;
            this.groupBoxLog.TabStop = false;
            this.groupBoxLog.Text = "Nhat ky su kien (log)";

            // txtLog
            this.txtLog.BackColor = System.Drawing.SystemColors.Window;
            this.txtLog.Dock = System.Windows.Forms.DockStyle.Fill;
            this.txtLog.Font = new System.Drawing.Font("Consolas", 9F);
            this.txtLog.Location = new System.Drawing.Point(3, 19);
            this.txtLog.Multiline = true;
            this.txtLog.Name = "txtLog";
            this.txtLog.ReadOnly = true;
            this.txtLog.ScrollBars = System.Windows.Forms.ScrollBars.Vertical;
            this.txtLog.Size = new System.Drawing.Size(954, 210);
            this.txtLog.TabIndex = 0;

            // ---------- MainForm ----------
            this.AutoScaleDimensions = new System.Drawing.SizeF(7F, 15F);
            this.AutoScaleMode = System.Windows.Forms.AutoScaleMode.Font;
            this.ClientSize = new System.Drawing.Size(960, 760);
            // Thu tu them vao quan trong: control Dock=Fill phai duoc them truoc.
            // Docking duyet nguoc thu tu them vao, nen control duoc them sau cung
            // (panelTop) se chiem vi tri tren cung, roi lan luot xuong duoi.
            this.Controls.Add(this.groupBoxLog);
            this.Controls.Add(this.groupBoxSend);
            this.Controls.Add(this.groupBoxStations);
            this.Controls.Add(this.panelTop);
            this.MinimumSize = new System.Drawing.Size(860, 700);
            this.Name = "MainForm";
            this.StartPosition = System.Windows.Forms.FormStartPosition.CenterScreen;
            this.Text = "LAN Monitor - Server";
            this.panelTop.ResumeLayout(false);
            this.panelTop.PerformLayout();
            ((System.ComponentModel.ISupportInitialize)(this.numPort)).EndInit();
            this.groupBoxStations.ResumeLayout(false);
            ((System.ComponentModel.ISupportInitialize)(this.dgvStations)).EndInit();
            this.groupBoxSend.ResumeLayout(false);
            this.groupBoxSend.PerformLayout();
            this.groupBoxLog.ResumeLayout(false);
            this.groupBoxLog.PerformLayout();
            this.ResumeLayout(false);
        }
    }
}
