# Print Management System - Complete Installation Guide

## Overview
This guide covers the complete setup of your print management system with print driver integration, MFP scanning, and secure printing capabilities.

## 1. Print Driver Integration Setup

### A. Install Required Dependencies
```bash
# Install CUPS and related packages
sudo apt update
sudo apt install -y cups cups-client cups-bsd cups-filters

# Install Python packages for print handling
pip install pyipp python-cups pycups

# Load environment variables from a `.env` file
pip install python-dotenv

# Install additional print protocol support
sudo apt install -y samba-client cifs-utils
```

Make sure a `.env` file exists with required configuration values such as
`DATABASE_URL` and `SESSION_SECRET`. The application uses `python-dotenv` and
invokes `load_dotenv()` during startup to load these variables.

### B. Configure CUPS for Print Management
```bash
# Start and enable CUPS
sudo systemctl enable cups
sudo systemctl start cups

# Add print management user to CUPS admin group
sudo usermod -a -G lpadmin $USER

# Configure CUPS to listen on network
sudo nano /etc/cups/cupsd.conf
```

Add the following to `/etc/cups/cupsd.conf`:
```
# Listen on all interfaces
Listen *:631
DefaultEncryption Never
WebInterface Yes

# Allow access from local network
<Location />
  Order allow,deny
  Allow @LOCAL
</Location>

<Location /admin>
  Order allow,deny
  Allow @LOCAL
</Location>
```

### C. Create Universal Print Queues
```bash
# Create managed print queues that route through your system
lpadmin -p PrintManager_Default -E -v ipp://localhost:5000/printers/default
lpadmin -p PrintManager_Color -E -v ipp://localhost:5000/printers/color
lpadmin -p PrintManager_BW -E -v ipp://localhost:5000/printers/bw

# Set default print options
lpoptions -p PrintManager_Default -o sides=two-sided-long-edge
lpoptions -p PrintManager_Color -o ColorModel=RGB
lpoptions -p PrintManager_BW -o ColorModel=Gray
```

### D. Start Print Driver Integration Service
```bash
# Run the print driver integration service
python3 print_driver_integration.py &

# Or add to systemd for automatic startup
sudo cp print_driver_service.service /etc/systemd/system/
sudo systemctl enable print_driver_service
sudo systemctl start print_driver_service
```

## 2. MFP Scanning Integration Setup

### A. Install Scanning Dependencies
```bash
# Install OCR and image processing libraries
sudo apt install -y tesseract-ocr tesseract-ocr-eng python3-opencv
pip install pytesseract Pillow PyMuPDF

# Install SANE for scanner support
sudo apt install -y sane-utils libsane-extras

# Install network scanning protocols
sudo apt install -y xinetd
```

### B. Configure Network Scanning Services
```bash
# Setup FTP server for scan-to-FTP
sudo apt install -y vsftpd
sudo nano /etc/vsftpd.conf
```

Add to `/etc/vsftpd.conf`:
```
# Enable scanning uploads
write_enable=YES
local_enable=YES
chroot_local_user=YES
allow_writeable_chroot=YES

# Create scan upload directory
user_sub_token=$USER
local_root=/scans/$USER
```

### C. Configure Email-to-Scan
```bash
# Install email server components
sudo apt install -y postfix dovecot-imapd

# Configure postfix for scan emails
sudo nano /etc/postfix/main.cf
```

Add scanning email configuration:
```
# Scan-to-email configuration
virtual_alias_domains = scan.company.com
virtual_alias_maps = hash:/etc/postfix/virtual

# Create virtual aliases file
sudo nano /etc/postfix/virtual
```

### D. Start MFP Integration Service
```bash
# Run the MFP scan integration service
python3 mfp_scan_integration.py &

# Configure for systemd
sudo cp mfp_scan_service.service /etc/systemd/system/
sudo systemctl enable mfp_scan_service
sudo systemctl start mfp_scan_service
```

## 3. Secure Printing Setup

### A. Install Security Dependencies
```bash
# Install cryptographic libraries
pip install cryptography qrcode[pil] pynacl

# Install smart card support (optional)
sudo apt install -y pcscd pcsc-tools libccid

# Install RFID/NFC support (optional)
sudo apt install -y libnfc-bin libnfc-examples
```

### B. Configure Authentication Methods

#### Card/Badge Authentication
```bash
# Setup card reader service
sudo nano /etc/systemd/system/card-reader.service
```

```ini
[Unit]
Description=Card Reader Service for Secure Printing
After=network.target

[Service]
Type=simple
User=printmanager
ExecStart=/usr/bin/python3 /path/to/card_reader_service.py
Restart=always

[Install]
WantedBy=multi-user.target
```

#### PIN Authentication
Configure PIN storage (use proper encryption in production):
```python
# In your application configuration
SECURE_PRINT_CONFIG = {
    'pin_hash_algorithm': 'scrypt',
    'pin_salt_length': 32,
    'session_timeout_minutes': 5,
    'max_authentication_attempts': 3
}
```

### C. Start Secure Printing Service
```bash
# Run the secure printing service
python3 secure_printing.py &

# Add to systemd
sudo cp secure_print_service.service /etc/systemd/system/
sudo systemctl enable secure_print_service
sudo systemctl start secure_print_service
```

## 4. MFP Device Configuration

### Canon imageRUNNER ADVANCE Series
1. Access device web interface (https://printer-ip)
2. Go to Settings > Network > TCP/IP Settings
3. Configure scan destinations:
   - **Scan to Email**: SMTP server = your-server.com:587
   - **Scan to SMB**: \\\\your-server\\scans
   - **Scan to FTP**: ftp://your-server.com/scans/
   - **Scan to WebDAV**: http://your-server:8080/scan/upload

### Xerox WorkCentre Series
1. Access CentreWare Internet Services
2. Configure Services > Scan Services
3. Add repositories:
   - **Email Repository**: SMTP settings
   - **Network Repository**: SMB/FTP settings
   - **Web Services Repository**: HTTP endpoint

### HP LaserJet Enterprise MFP
1. Access HP Web Jetadmin or device panel
2. Configure Digital Sending
3. Setup destinations:
   - **Email**: SMTP configuration
   - **Network Folder**: SMB share settings
   - **Web Services**: HTTP POST endpoint

## 5. Network Configuration

### Firewall Rules
```bash
# Allow print management ports
sudo ufw allow 631/tcp    # IPP
sudo ufw allow 515/tcp    # LPD
sudo ufw allow 9100/tcp   # Raw printing
sudo ufw allow 8080/tcp   # Scan web service
sudo ufw allow 21/tcp     # FTP for scanning
sudo ufw allow 445/tcp    # SMB for scanning
```

### DNS Configuration
Add these DNS entries for your domain:
```
print.company.com       A       your-server-ip
scan.company.com        A       your-server-ip
*.scan.company.com      A       your-server-ip
```

## 6. User Setup and Training

### A. Create User Accounts
```bash
# Add users to print management system
python3 manage.py add-user --username=john.doe --email=john.doe@company.com --department=IT
python3 manage.py add-user --username=jane.smith --email=jane.smith@company.com --department=HR
```

### B. Configure User Permissions
```bash
# Set print quotas and permissions
python3 manage.py set-quota --user=john.doe --pages=1000 --color-pages=100
python3 manage.py set-permissions --user=jane.smith --secure-print=true --scan-access=true
```

### C. Generate User Documentation
Create quick reference cards with:
- Print driver installation instructions
- Secure print codes usage
- Scan-to-email addresses
- Mobile app QR codes

## 7. Monitoring and Maintenance

### A. Setup Log Monitoring
```bash
# Configure log rotation
sudo nano /etc/logrotate.d/printmanager
```

```
/var/log/printmanager/*.log {
    daily
    missingok
    rotate 52
    compress
    notifempty
    create 644 printmanager printmanager
}
```

### B. Create Monitoring Dashboard
Monitor these key metrics:
- Print job queue status
- Printer availability
- User authentication success/failure rates
- Scan processing times
- Security audit events

### C. Backup Strategy
```bash
# Database backup
pg_dump printmanager > /backups/printmanager_$(date +%Y%m%d).sql

# Configuration backup
tar -czf /backups/config_$(date +%Y%m%d).tar.gz /etc/cups/ /etc/sane.d/ /path/to/app/config/

# User files backup
rsync -av /uploads/ /backups/uploads/
```

## 8. Testing and Validation

### A. Test Print Driver Integration
```bash
# Test print submission
echo "Test page" | lp -d PrintManager_Default

# Verify job appears in management system
curl http://localhost:5000/api/jobs | jq
```

### B. Test MFP Scanning
```bash
# Test scan upload endpoint
curl -X POST -F "scan_file=@test.pdf" -F "user_code=john.doe" \
     http://localhost:8080/scan/upload
```

### C. Test Secure Printing
```bash
# Submit secure print job
curl -X POST -H "Content-Type: application/json" \
     -d '{"user_id":1,"file_path":"/test.pdf","print_options":{}}' \
     http://localhost:5000/api/secure-print/submit
```

## 9. Production Deployment

### A. SSL/TLS Configuration
```bash
# Install SSL certificates
sudo apt install -y certbot
sudo certbot --nginx -d print.company.com

# Configure CUPS with SSL
sudo nano /etc/cups/cupsd.conf
# Add: DefaultEncryption Required
```

### B. Database Security
```bash
# Secure PostgreSQL
sudo -u postgres psql -c "ALTER USER printmanager WITH PASSWORD 'strong-password';"

# Configure SSL connections
sudo nano /etc/postgresql/*/main/postgresql.conf
# Add: ssl = on
```

### C. Application Security
```python
# Production configuration
PRODUCTION_CONFIG = {
    'SECRET_KEY': 'your-secret-key',
    'DATABASE_URL': 'postgresql://user:pass@localhost/printmanager',
    'CUPS_SERVER': 'localhost:631',
    'SECURE_PRINT_ENCRYPTION': True,
    'AUDIT_LOGGING': True,
    'MAX_FILE_SIZE': '50MB',
    'ALLOWED_FILE_TYPES': ['.pdf', '.doc', '.docx', '.txt', '.jpg', '.png']
}
```

## 10. Troubleshooting Common Issues

### Print Jobs Not Appearing
1. Check CUPS service status: `sudo systemctl status cups`
2. Verify printer queues: `lpstat -p`
3. Check print management logs: `tail -f /var/log/printmanager/app.log`

### Scanning Not Working
1. Test scan endpoint: `curl http://localhost:8080/scan/upload`
2. Check MFP network connectivity
3. Verify scan destination permissions

### Authentication Failures
1. Check secure print service: `sudo systemctl status secure_print_service`
2. Verify user credentials in database
3. Check authentication logs

## 11. Advanced Features

### A. Cloud Integration
- Office 365 integration for scan-to-OneDrive
- Google Workspace integration for scan-to-Drive
- AWS S3 integration for document archival

### B. Mobile App Development
- React Native app for iOS/Android
- QR code scanning for quick print release
- Push notifications for job completion

### C. API Extensions
- REST API for third-party integrations
- Webhook support for external systems
- GraphQL API for complex queries

This comprehensive setup provides enterprise-grade print management with modern security features and integration capabilities.