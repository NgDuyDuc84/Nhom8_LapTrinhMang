namespace Client
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
        private System.Windows.Forms.Label lblHost;
        private System.Windows.Forms.TextBox txtHost;
        private System.Windows.Forms.Label lblPort;
        private System.Windows.Forms.NumericUpDown numPort;
        private System.Windows.Forms.Label lblName;
        private System.Windows.Forms.TextBox txtName;
        private System.Windows.Forms.Button btnConnect;
        private System.Windows.Forms.Button btnDisconnect;
        private System.Windows.Forms.Label lblStatus;
        private System.Windows.Forms.GroupBox groupBoxLog;
        private System.Windows.Forms.TextBox txtLog;

        private void InitializeComponent()
        {
            this.panelTop = new System.Windows.Forms.Panel();
            this.lblHost = new System.Windows.Forms.Label();
            this.txtHost = new System.Windows.Forms.TextBox();
            this.lblPort = new System.Windows.Forms.Label();
            this.numPort = new System.Windows.Forms.NumericUpDown();
            this.lblName = new System.Windows.Forms.Label();
            this.txtName = new System.Windows.Forms.TextBox();
            this.btnConnect = new System.Windows.Forms.Button();
            this.btnDisconnect = new System.Windows.Forms.Button();
            this.lblStatus = new System.Windows.Forms.Label();
            this.groupBoxLog = new System.Windows.Forms.GroupBox();
            this.txtLog = new System.Windows.Forms.TextBox();
            this.panelTop.SuspendLayout();
            ((System.ComponentModel.ISupportInitialize)(this.numPort)).BeginInit();
            this.groupBoxLog.SuspendLayout();
            this.SuspendLayout();

            // ---------- panelTop: thong tin ket noi ----------
            this.panelTop.Controls.Add(this.lblStatus);
            this.panelTop.Controls.Add(this.btnDisconnect);
            this.panelTop.Controls.Add(this.btnConnect);
            this.panelTop.Controls.Add(this.txtName);
            this.panelTop.Controls.Add(this.lblName);
            this.panelTop.Controls.Add(this.numPort);
            this.panelTop.Controls.Add(this.lblPort);
            this.panelTop.Controls.Add(this.txtHost);
            this.panelTop.Controls.Add(this.lblHost);
            this.panelTop.Dock = System.Windows.Forms.DockStyle.Top;
            this.panelTop.Location = new System.Drawing.Point(0, 0);
            this.panelTop.Name = "panelTop";
            this.panelTop.Size = new System.Drawing.Size(784, 92);
            this.panelTop.TabIndex = 0;

            // lblHost
            this.lblHost.AutoSize = true;
            this.lblHost.Location = new System.Drawing.Point(12, 16);
            this.lblHost.Name = "lblHost";
            this.lblHost.Size = new System.Drawing.Size(100, 15);
            this.lblHost.TabIndex = 0;
            this.lblHost.Text = "Dia chi Server:";

            // txtHost
            this.txtHost.Location = new System.Drawing.Point(120, 13);
            this.txtHost.Name = "txtHost";
            this.txtHost.Size = new System.Drawing.Size(140, 23);
            this.txtHost.TabIndex = 1;
            this.txtHost.Text = "127.0.0.1";

            // lblPort
            this.lblPort.AutoSize = true;
            this.lblPort.Location = new System.Drawing.Point(276, 16);
            this.lblPort.Name = "lblPort";
            this.lblPort.Size = new System.Drawing.Size(48, 15);
            this.lblPort.TabIndex = 2;
            this.lblPort.Text = "Cong:";

            // numPort
            this.numPort.Location = new System.Drawing.Point(326, 13);
            this.numPort.Maximum = new decimal(new int[] { 65535, 0, 0, 0 });
            this.numPort.Minimum = new decimal(new int[] { 1, 0, 0, 0 });
            this.numPort.Name = "numPort";
            this.numPort.Size = new System.Drawing.Size(70, 23);
            this.numPort.TabIndex = 3;
            this.numPort.Value = new decimal(new int[] { 5000, 0, 0, 0 });

            // lblName
            this.lblName.AutoSize = true;
            this.lblName.Location = new System.Drawing.Point(412, 16);
            this.lblName.Name = "lblName";
            this.lblName.Size = new System.Drawing.Size(68, 15);
            this.lblName.TabIndex = 4;
            this.lblName.Text = "Ten may:";

            // txtName
            this.txtName.Location = new System.Drawing.Point(484, 13);
            this.txtName.Name = "txtName";
            this.txtName.Size = new System.Drawing.Size(160, 23);
            this.txtName.TabIndex = 5;

            // btnConnect
            this.btnConnect.Location = new System.Drawing.Point(12, 52);
            this.btnConnect.Name = "btnConnect";
            this.btnConnect.Size = new System.Drawing.Size(150, 28);
            this.btnConnect.TabIndex = 6;
            this.btnConnect.Text = "&Ket noi Server";
            this.btnConnect.UseVisualStyleBackColor = true;
            this.btnConnect.Click += new System.EventHandler(this.btnConnect_Click);

            // btnDisconnect
            this.btnDisconnect.Enabled = false;
            this.btnDisconnect.Location = new System.Drawing.Point(172, 52);
            this.btnDisconnect.Name = "btnDisconnect";
            this.btnDisconnect.Size = new System.Drawing.Size(140, 28);
            this.btnDisconnect.TabIndex = 7;
            this.btnDisconnect.Text = "N&gat ket noi";
            this.btnDisconnect.UseVisualStyleBackColor = true;
            this.btnDisconnect.Click += new System.EventHandler(this.btnDisconnect_Click);

            // lblStatus
            this.lblStatus.AutoSize = true;
            this.lblStatus.Location = new System.Drawing.Point(330, 58);
            this.lblStatus.Name = "lblStatus";
            this.lblStatus.Size = new System.Drawing.Size(90, 15);
            this.lblStatus.TabIndex = 8;
            this.lblStatus.Text = "Chua ket noi";

            // ---------- groupBoxLog: thong bao nhan duoc ----------
            this.groupBoxLog.Controls.Add(this.txtLog);
            this.groupBoxLog.Dock = System.Windows.Forms.DockStyle.Fill;
            this.groupBoxLog.Location = new System.Drawing.Point(0, 92);
            this.groupBoxLog.Name = "groupBoxLog";
            this.groupBoxLog.Size = new System.Drawing.Size(784, 369);
            this.groupBoxLog.TabIndex = 2;
            this.groupBoxLog.TabStop = false;
            this.groupBoxLog.Text = "Thong bao nhan duoc / nhat ky";

            // txtLog
            this.txtLog.BackColor = System.Drawing.SystemColors.Window;
            this.txtLog.Dock = System.Windows.Forms.DockStyle.Fill;
            this.txtLog.Font = new System.Drawing.Font("Consolas", 9F);
            this.txtLog.Location = new System.Drawing.Point(3, 19);
            this.txtLog.Multiline = true;
            this.txtLog.Name = "txtLog";
            this.txtLog.ReadOnly = true;
            this.txtLog.ScrollBars = System.Windows.Forms.ScrollBars.Vertical;
            this.txtLog.Size = new System.Drawing.Size(778, 347);
            this.txtLog.TabIndex = 0;

            // ---------- MainForm ----------
            this.AutoScaleDimensions = new System.Drawing.SizeF(7F, 15F);
            this.AutoScaleMode = System.Windows.Forms.AutoScaleMode.Font;
            this.ClientSize = new System.Drawing.Size(784, 461);
            this.Controls.Add(this.groupBoxLog);
            this.Controls.Add(this.panelTop);
            this.MinimumSize = new System.Drawing.Size(660, 420);
            this.Name = "MainForm";
            this.StartPosition = System.Windows.Forms.FormStartPosition.CenterScreen;
            this.Text = "LAN Monitor - Client (May tram)";
            this.panelTop.ResumeLayout(false);
            this.panelTop.PerformLayout();
            ((System.ComponentModel.ISupportInitialize)(this.numPort)).EndInit();
            this.groupBoxLog.ResumeLayout(false);
            this.groupBoxLog.PerformLayout();
            this.ResumeLayout(false);
        }
    }
}
