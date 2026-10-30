using System;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.Reflection;
using System.Threading.Tasks;
using System.Windows.Forms;

namespace ProtonNextInstaller;

internal class MainForm : Form
{
    private readonly bool _isUninstallMode;
    private int _currentPage = 0; // 0=Welcome, 1=Directory, 2=Installing, 3=Finished

    // UI Panels
    private Panel _pnlHeader = null!;
    private Label _lblHeaderTitle = null!;
    private Label _lblHeaderSub = null!;
    private PictureBox _picHeaderIcon = null!;

    private Panel _pnlBottom = null!;
    private Label _lblBranding = null!;
    private Button _btnBack = null!;
    private Button _btnNext = null!;
    private Button _btnCancel = null!;

    private Panel _pnlContainer = null!;

    // Page 0: Welcome
    private Panel _pnlWelcome = null!;
    private Label _lblWelcomeTitle = null!;
    private Label _lblWelcomeText = null!;
    private Panel _pnlWelcomeSidebar = null!;

    // Page 1: Directory
    private Panel _pnlDirectory = null!;
    private TextBox _txtInstallDir = null!;
    private Button _btnBrowse = null!;
    private Label _lblSpaceRequired = null!;
    private Label _lblSpaceAvailable = null!;

    // Page 2: Installing
    private Panel _pnlInstalling = null!;
    private Label _lblStatus = null!;
    private ProgressBar _progressBar = null!;
    private Button _btnShowDetails = null!;
    private ListBox _lstDetails = null!;

    // Page 3: Finished
    private Panel _pnlFinished = null!;
    private Label _lblFinishedTitle = null!;
    private Label _lblFinishedText = null!;
    private CheckBox _chkRunApp = null!;
    private Panel _pnlFinishedSidebar = null!;

    private Image? _appIconImage;
    private readonly string? _customDir;

    public MainForm(bool isUninstallMode, string? customDir = null)
    {
        _isUninstallMode = isUninstallMode;
        _customDir = customDir;
        InitializeComponents();
        SetPage(0);
    }

    private void InitializeComponents()
    {
        SuspendLayout();

        Text = _isUninstallMode ? "ProtonNext Uninstall" : "ProtonNext Setup";
        ClientSize = new Size(505, 385);
        FormBorderStyle = FormBorderStyle.FixedDialog;
        MaximizeBox = false;
        StartPosition = FormStartPosition.CenterScreen;
        Font = new Font("Segoe UI", 9f, FontStyle.Regular, GraphicsUnit.Point);
        BackColor = SystemColors.Control;

        try
        {
            Icon = Icon.ExtractAssociatedIcon(Environment.ProcessPath ?? string.Empty) ?? SystemIcons.Application;
            _appIconImage = Icon?.ToBitmap();
        }
        catch
        {
            _appIconImage = null;
        }

        // Top Header
        _pnlHeader = new Panel
        {
            Dock = DockStyle.Top,
            Height = 62,
            BackColor = Color.White
        };
        _pnlHeader.Paint += (s, e) =>
        {
            using var pen = new Pen(Color.FromArgb(215, 215, 215));
            e.Graphics.DrawLine(pen, 0, _pnlHeader.Height - 1, _pnlHeader.Width, _pnlHeader.Height - 1);
        };

        _lblHeaderTitle = new Label
        {
            Location = new Point(18, 11),
            AutoSize = true,
            Font = new Font("Segoe UI", 9f, FontStyle.Bold),
            ForeColor = Color.Black,
            Text = "Choose Install Location"
        };

        _lblHeaderSub = new Label
        {
            Location = new Point(34, 30),
            AutoSize = true,
            Font = new Font("Segoe UI", 8.5f),
            ForeColor = Color.FromArgb(60, 60, 60),
            Text = "Choose the folder in which to install ProtonNext."
        };

        _picHeaderIcon = new PictureBox
        {
            Location = new Point(452, 12),
            Size = new Size(38, 38),
            SizeMode = PictureBoxSizeMode.Zoom,
            Image = _appIconImage
        };

        _pnlHeader.Controls.AddRange([_lblHeaderTitle, _lblHeaderSub, _picHeaderIcon]);

        // Bottom Button Bar
        _pnlBottom = new Panel
        {
            Dock = DockStyle.Bottom,
            Height = 46,
            BackColor = SystemColors.Control
        };
        _pnlBottom.Paint += (s, e) =>
        {
            using var pen = new Pen(Color.FromArgb(215, 215, 215));
            e.Graphics.DrawLine(pen, 0, 0, _pnlBottom.Width, 0);
        };

        _lblBranding = new Label
        {
            Location = new Point(12, 15),
            AutoSize = true,
            ForeColor = Color.FromArgb(120, 120, 120),
            Font = new Font("Segoe UI", 8f),
            Text = "Nullsoft Install System v3.08"
        };

        _btnBack = new Button
        {
            Location = new Point(255, 11),
            Size = new Size(75, 24),
            Text = "< Back",
            UseVisualStyleBackColor = true
        };
        _btnBack.Click += (s, e) => { if (_currentPage > 0) SetPage(_currentPage - 1); };

        _btnNext = new Button
        {
            Location = new Point(336, 11),
            Size = new Size(75, 24),
            Text = "Next >",
            UseVisualStyleBackColor = true
        };
        _btnNext.Click += async (s, e) => await OnNextClickedAsync();

        _btnCancel = new Button
        {
            Location = new Point(418, 11),
            Size = new Size(75, 24),
            Text = "Cancel",
            UseVisualStyleBackColor = true
        };
        _btnCancel.Click += (s, e) => Close();

        _pnlBottom.Controls.AddRange([_lblBranding, _btnBack, _btnNext, _btnCancel]);

        // Main Container
        _pnlContainer = new Panel
        {
            Dock = DockStyle.Fill
        };

        BuildWelcomePage();
        BuildDirectoryPage();
        BuildInstallingPage();
        BuildFinishedPage();

        Controls.AddRange([_pnlContainer, _pnlHeader, _pnlBottom]);
        ResumeLayout(false);
    }

    private void BuildWelcomePage()
    {
        _pnlWelcome = new Panel { Dock = DockStyle.Fill, Visible = false };

        _pnlWelcomeSidebar = new Panel
        {
            Dock = DockStyle.Left,
            Width = 160,
            BackColor = Color.FromArgb(109, 74, 255) // Proton violet
        };
        _pnlWelcomeSidebar.Paint += (s, e) =>
        {
            if (_appIconImage != null)
            {
                e.Graphics.DrawImage(_appIconImage, new Rectangle(48, 50, 64, 64));
            }
            using var font = new Font("Segoe UI", 12f, FontStyle.Bold);
            using var brush = new SolidBrush(Color.White);
            e.Graphics.DrawString("ProtonNext", font, brush, 36, 130);
        };

        var rightPanel = new Panel { Dock = DockStyle.Fill, Padding = new Padding(20, 25, 20, 20) };
        _lblWelcomeTitle = new Label
        {
            Location = new Point(20, 25),
            Size = new Size(300, 48),
            Font = new Font("Segoe UI", 12f, FontStyle.Bold),
            ForeColor = Color.Black,
            Text = _isUninstallMode
                ? "Welcome to the ProtonNext Uninstall Wizard"
                : "Welcome to the ProtonNext Setup Wizard"
        };

        _lblWelcomeText = new Label
        {
            Location = new Point(20, 85),
            Size = new Size(300, 180),
            Font = new Font("Segoe UI", 9f),
            ForeColor = Color.FromArgb(40, 40, 40),
            Text = _isUninstallMode
                ? "This wizard will guide you through the uninstallation of ProtonNext.\n\nBefore starting the uninstallation, make sure ProtonNext is not running.\n\nClick Next to continue."
                : "This wizard will guide you through the installation of ProtonNext.\n\nIt is recommended that you close all other applications before starting Setup. This will make it possible to update relevant system files without having to reboot your computer.\n\nClick Next to continue."
        };

        rightPanel.Controls.AddRange([_lblWelcomeTitle, _lblWelcomeText]);
        _pnlWelcome.Controls.AddRange([rightPanel, _pnlWelcomeSidebar]);
        _pnlContainer.Controls.Add(_pnlWelcome);
    }

    private void BuildDirectoryPage()
    {
        _pnlDirectory = new Panel { Dock = DockStyle.Fill, Visible = false, Padding = new Padding(25, 15, 25, 15) };

        var lblIntro = new Label
        {
            Location = new Point(25, 15),
            Size = new Size(455, 45),
            Text = _isUninstallMode
                ? "ProtonNext will be uninstalled from the following folder. Click Uninstall to start the uninstallation."
                : "Setup will install ProtonNext in the following folder. To install in a different folder, click Browse and select another folder. Click Install to start the installation."
        };

        var grpFolder = new GroupBox
        {
            Location = new Point(25, 68),
            Size = new Size(455, 65),
            Text = "Destination Folder"
        };

        _txtInstallDir = new TextBox
        {
            Location = new Point(14, 25),
            Size = new Size(345, 23),
            Text = !string.IsNullOrWhiteSpace(_customDir) ? _customDir : InstallerEngine.DefaultInstallDir,
            ReadOnly = _isUninstallMode
        };
        _txtInstallDir.TextChanged += (s, e) => UpdateDriveSpace();

        _btnBrowse = new Button
        {
            Location = new Point(366, 24),
            Size = new Size(75, 25),
            Text = "Browse...",
            Visible = !_isUninstallMode
        };
        _btnBrowse.Click += (s, e) =>
        {
            using var dlg = new FolderBrowserDialog();
            dlg.SelectedPath = _txtInstallDir.Text;
            if (dlg.ShowDialog() == DialogResult.OK)
            {
                _txtInstallDir.Text = Path.Combine(dlg.SelectedPath, "ProtonNext");
            }
        };

        grpFolder.Controls.AddRange([_txtInstallDir, _btnBrowse]);

        _lblSpaceRequired = new Label
        {
            Location = new Point(25, 150),
            AutoSize = true,
            Text = "Space required: 366.2 MB",
            Visible = !_isUninstallMode
        };

        _lblSpaceAvailable = new Label
        {
            Location = new Point(25, 172),
            AutoSize = true,
            Text = "Space available: Calculating...",
            Visible = !_isUninstallMode
        };

        _pnlDirectory.Controls.AddRange([lblIntro, grpFolder, _lblSpaceRequired, _lblSpaceAvailable]);
        _pnlContainer.Controls.Add(_pnlDirectory);
    }

    private void UpdateDriveSpace()
    {
        try
        {
            string root = Path.GetPathRoot(_txtInstallDir.Text) ?? "C:\\";
            var drive = new DriveInfo(root);
            double gb = drive.AvailableFreeSpace / (1024.0 * 1024 * 1024);
            _lblSpaceAvailable.Text = $"Space available: {gb:F1} GB";
        }
        catch
        {
            _lblSpaceAvailable.Text = "Space available: Unknown";
        }
    }

    private void BuildInstallingPage()
    {
        _pnlInstalling = new Panel { Dock = DockStyle.Fill, Visible = false, Padding = new Padding(25, 15, 25, 15) };

        _lblStatus = new Label
        {
            Location = new Point(25, 15),
            Size = new Size(455, 20),
            Text = _isUninstallMode ? "Uninstalling..." : "Extracting: ProtonVPN.Client.exe"
        };

        _progressBar = new ProgressBar
        {
            Location = new Point(25, 40),
            Size = new Size(455, 20),
            Style = ProgressBarStyle.Continuous
        };

        _btnShowDetails = new Button
        {
            Location = new Point(380, 68),
            Size = new Size(100, 24),
            Text = "Show details"
        };
        _btnShowDetails.Click += (s, e) =>
        {
            _lstDetails.Visible = !_lstDetails.Visible;
            _btnShowDetails.Text = _lstDetails.Visible ? "Hide details" : "Show details";
        };

        _lstDetails = new ListBox
        {
            Location = new Point(25, 98),
            Size = new Size(455, 160),
            Font = new Font("Consolas", 8f),
            HorizontalScrollbar = true,
            Visible = false
        };

        _pnlInstalling.Controls.AddRange([_lblStatus, _progressBar, _btnShowDetails, _lstDetails]);
        _pnlContainer.Controls.Add(_pnlInstalling);
    }

    private void BuildFinishedPage()
    {
        _pnlFinished = new Panel { Dock = DockStyle.Fill, Visible = false };

        _pnlFinishedSidebar = new Panel
        {
            Dock = DockStyle.Left,
            Width = 160,
            BackColor = Color.FromArgb(109, 74, 255)
        };
        _pnlFinishedSidebar.Paint += (s, e) =>
        {
            if (_appIconImage != null)
            {
                e.Graphics.DrawImage(_appIconImage, new Rectangle(48, 50, 64, 64));
            }
            using var font = new Font("Segoe UI", 12f, FontStyle.Bold);
            using var brush = new SolidBrush(Color.White);
            e.Graphics.DrawString("ProtonNext", font, brush, 36, 130);
        };

        var rightPanel = new Panel { Dock = DockStyle.Fill, Padding = new Padding(20, 25, 20, 20) };
        _lblFinishedTitle = new Label
        {
            Location = new Point(20, 25),
            Size = new Size(300, 48),
            Font = new Font("Segoe UI", 12f, FontStyle.Bold),
            ForeColor = Color.Black,
            Text = _isUninstallMode
                ? "Completing the ProtonNext Uninstall Wizard"
                : "Completing the ProtonNext Setup Wizard"
        };

        _lblFinishedText = new Label
        {
            Location = new Point(20, 85),
            Size = new Size(300, 70),
            Font = new Font("Segoe UI", 9f),
            ForeColor = Color.FromArgb(40, 40, 40),
            Text = _isUninstallMode
                ? "ProtonNext has been uninstalled from your computer.\n\nClick Finish to close this wizard."
                : "ProtonNext has been installed on your computer.\n\nClick Finish to close Setup."
        };

        _chkRunApp = new CheckBox
        {
            Location = new Point(20, 165),
            Size = new Size(300, 24),
            Text = "Launch ProtonNext",
            Checked = true,
            Visible = !_isUninstallMode
        };

        rightPanel.Controls.AddRange([_lblFinishedTitle, _lblFinishedText, _chkRunApp]);
        _pnlFinished.Controls.AddRange([rightPanel, _pnlFinishedSidebar]);
        _pnlContainer.Controls.Add(_pnlFinished);
    }

    private void SetPage(int page)
    {
        _currentPage = page;

        _pnlWelcome.Visible = (page == 0);
        _pnlDirectory.Visible = (page == 1);
        _pnlInstalling.Visible = (page == 2);
        _pnlFinished.Visible = (page == 3);

        // Header visibility (hidden on welcome and finish)
        _pnlHeader.Visible = (page == 1 || page == 2);

        if (page == 1)
        {
            UpdateDriveSpace();
            _lblHeaderTitle.Text = _isUninstallMode ? "Uninstall ProtonNext" : "Choose Install Location";
            _lblHeaderSub.Text = _isUninstallMode ? "Remove ProtonNext from your computer." : "Choose the folder in which to install ProtonNext.";
            _btnBack.Enabled = true;
            _btnNext.Text = _isUninstallMode ? "Uninstall" : "Install";
        }
        else if (page == 2)
        {
            _lblHeaderTitle.Text = _isUninstallMode ? "Uninstalling" : "Installing";
            _lblHeaderSub.Text = _isUninstallMode ? "Please wait while ProtonNext is being uninstalled." : "Please wait while ProtonNext is being installed.";
            _btnBack.Enabled = false;
            _btnNext.Enabled = false;
            _btnCancel.Enabled = false;
        }
        else if (page == 3)
        {
            _btnBack.Visible = false;
            _btnNext.Enabled = true;
            _btnNext.Text = "Finish";
            _btnCancel.Visible = false;
        }
        else
        {
            _btnBack.Enabled = false;
            _btnNext.Text = "Next >";
        }
    }

    private async Task OnNextClickedAsync()
    {
        if (_currentPage == 0)
        {
            SetPage(1);
        }
        else if (_currentPage == 1)
        {
            SetPage(2);
            await ExecuteInstallationOrUninstallationAsync();
        }
        else if (_currentPage == 3)
        {
            if (!_isUninstallMode && _chkRunApp.Checked)
            {
                string clientExe = Path.Combine(_txtInstallDir.Text, "ProtonVPN.Client.exe");
                if (File.Exists(clientExe))
                {
                    try
                    {
                        Process.Start(new ProcessStartInfo
                        {
                            FileName = clientExe,
                            WorkingDirectory = _txtInstallDir.Text,
                            UseShellExecute = true
                        });
                    }
                    catch { }
                }
            }
            Close();
        }
    }

    private async Task ExecuteInstallationOrUninstallationAsync()
    {
        string installDir = _txtInstallDir.Text;

        if (_isUninstallMode)
        {
            await Task.Run(() =>
            {
                InstallerEngine.Uninstall(installDir, log =>
                {
                    Invoke(() =>
                    {
                        _lblStatus.Text = log;
                        _lstDetails.Items.Add(log);
                        _lstDetails.TopIndex = _lstDetails.Items.Count - 1;
                    });
                });
            });

            _progressBar.Value = 100;
            SetPage(3);
        }
        else
        {
            await Task.Run(() =>
            {
                InstallerEngine.Install(
                    installDir,
                    onProgress: (current, total, file) =>
                    {
                        if (current % 10 == 0 || current == total)
                        {
                            Invoke(() =>
                            {
                                int pct = (int)((double)current / total * 100);
                                _progressBar.Value = Math.Clamp(pct, 0, 100);
                                _lblStatus.Text = $"Extracting: {file}";
                            });
                        }
                    },
                    onLog: log =>
                    {
                        Invoke(() =>
                        {
                            _lstDetails.Items.Add(log);
                            _lstDetails.TopIndex = _lstDetails.Items.Count - 1;
                        });
                    });
            });

            _progressBar.Value = 100;
            _lblStatus.Text = "Completed";
            SetPage(3);
        }
    }
}
