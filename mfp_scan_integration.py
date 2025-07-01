"""
MFP (Multi-Function Printer) Scan Integration Module
Handles scan-to-email, scan-to-folder, and scan-to-server functionality
"""

import socket
import smtplib
import os
import json
import threading
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from datetime import datetime
import requests
from app import db
from app.models import PrintJob, User

class MFPScanIntegration:
    """Handles MFP scanning protocols and workflows"""
    
    def __init__(self):
        self.ftp_port = 21
        self.smb_port = 445
        self.http_port = 8080  # Web service for scan reception
        self.email_server = None
        self.scan_destinations = {}
        
    def setup_scan_to_email(self, smtp_config):
        """Configure scan-to-email functionality"""
        self.email_config = {
            'smtp_server': smtp_config.get('server', 'localhost'),
            'smtp_port': smtp_config.get('port', 587),
            'username': smtp_config.get('username'),
            'password': smtp_config.get('password'),
            'use_tls': smtp_config.get('use_tls', True)
        }
        
        # Create email aliases for each user
        user_aliases = {}
        users = User.query.all()
        for user in users:
            user_aliases[user.email] = {
                'scan_email': f'scan.{user.username}@company.com',
                'default_format': 'PDF',
                'default_resolution': '300',
                'auto_ocr': True,
                'destinations': ['email', 'personal_folder']
            }
        
        return user_aliases
    
    def start_scan_web_service(self):
        """Start HTTP web service to receive scans from MFPs"""
        from flask import Flask, request, jsonify
        
        scan_app = Flask(__name__)
        
        @scan_app.route('/scan/upload', methods=['POST'])
        def receive_scan():
            try:
                # Get scan metadata
                user_code = request.form.get('user_code')
                scan_format = request.form.get('format', 'PDF')
                resolution = request.form.get('resolution', '300')
                color_mode = request.form.get('color_mode', 'color')
                duplex = request.form.get('duplex', 'false') == 'true'
                
                # Get uploaded file
                uploaded_file = request.files.get('scan_file')
                if not uploaded_file:
                    return jsonify({'error': 'No file uploaded'}), 400
                
                # Validate user
                user = User.query.filter_by(username=user_code).first()
                if not user:
                    return jsonify({'error': 'Invalid user code'}), 401
                
                # Save scan file
                filename = f"scan_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{user.username}.{scan_format.lower()}"
                file_path = os.path.join('/uploads/scans', filename)
                os.makedirs(os.path.dirname(file_path), exist_ok=True)
                uploaded_file.save(file_path)
                
                # Process scan based on user preferences
                self.process_scan(user, file_path, {
                    'format': scan_format,
                    'resolution': resolution,
                    'color_mode': color_mode,
                    'duplex': duplex
                })
                
                return jsonify({
                    'status': 'success',
                    'scan_id': filename,
                    'message': f'Scan processed for {user.username}'
                })
                
            except Exception as e:
                return jsonify({'error': str(e)}), 500
        
        @scan_app.route('/scan/destinations/<user_code>')
        def get_user_destinations(user_code):
            """Get available scan destinations for user"""
            user = User.query.filter_by(username=user_code).first()
            if not user:
                return jsonify({'error': 'Invalid user code'}), 401
            
            destinations = {
                'email': {
                    'name': 'Email to myself',
                    'address': user.email,
                    'icon': 'email'
                },
                'personal_folder': {
                    'name': 'Personal folder',
                    'path': f'/scans/{user.username}/',
                    'icon': 'folder'
                },
                'department_folder': {
                    'name': f'{user.department.name} shared folder',
                    'path': f'/scans/departments/{user.department.name}/',
                    'icon': 'folder-shared'
                } if user.department else None,
                'cloud_storage': {
                    'name': 'Cloud storage',
                    'providers': ['OneDrive', 'Google Drive', 'Dropbox'],
                    'icon': 'cloud'
                }
            }
            
            return jsonify({k: v for k, v in destinations.items() if v})
        
        # Start the web service in a separate thread
        threading.Thread(
            target=lambda: scan_app.run(host='0.0.0.0', port=self.http_port),
            daemon=True
        ).start()
        
        print(f"Scan web service started on port {self.http_port}")
    
    def setup_mfp_configurations(self):
        """Generate MFP configuration files for major brands"""
        
        # Canon imageRUNNER configuration
        canon_config = {
            'brand': 'Canon',
            'series': 'imageRUNNER ADVANCE',
            'scan_to_email': {
                'smtp_server': 'your-server.com',
                'smtp_port': 587,
                'authentication': 'enabled',
                'encryption': 'STARTTLS'
            },
            'scan_to_smb': {
                'server': '\\\\your-server\\scans',
                'authentication': 'domain',
                'folder_structure': 'user_based'
            },
            'scan_to_ftp': {
                'server': 'your-server.com',
                'port': 21,
                'passive_mode': True,
                'folder_structure': '/scans/{username}/'
            },
            'web_service': {
                'url': 'http://your-server:8080/scan/upload',
                'authentication': 'user_code',
                'supported_formats': ['PDF', 'JPEG', 'TIFF']
            }
        }
        
        # Xerox WorkCentre configuration
        xerox_config = {
            'brand': 'Xerox',
            'series': 'WorkCentre',
            'scan_repositories': [
                {
                    'name': 'PrintManager Server',
                    'type': 'WebDAV',
                    'url': 'http://your-server:8080/scan/webdav',
                    'authentication': 'basic'
                },
                {
                    'name': 'User Email',
                    'type': 'SMTP',
                    'server': 'your-server.com:587',
                    'authentication': 'user_credentials'
                }
            ],
            'workflow_scanning': {
                'invoice_processing': {
                    'destination': 'accounting@company.com',
                    'ocr': True,
                    'format': 'PDF/A'
                },
                'hr_documents': {
                    'destination': '/scans/hr/',
                    'encryption': True,
                    'retention': '7_years'
                }
            }
        }
        
        # HP LaserJet MFP configuration
        hp_config = {
            'brand': 'HP',
            'series': 'LaserJet Enterprise MFP',
            'digital_sending': {
                'email': {
                    'server': 'your-server.com',
                    'port': 587,
                    'authentication': 'SMTP_AUTH'
                },
                'network_folder': {
                    'protocol': 'SMB',
                    'server': '\\\\your-server\\scans',
                    'authentication': 'Windows'
                },
                'web_services': {
                    'url': 'http://your-server:8080/scan/upload',
                    'method': 'POST',
                    'authentication': 'basic'
                }
            },
            'security': {
                'secure_erase': True,
                'encryption_in_transit': True,
                'audit_logging': True
            }
        }
        
        return {
            'canon': canon_config,
            'xerox': xerox_config,
            'hp': hp_config
        }
    
    def process_scan(self, user, file_path, scan_options):
        """Process received scan based on user preferences"""
        try:
            # Apply OCR if requested
            if scan_options.get('ocr', False):
                self.apply_ocr(file_path)
            
            # Get user destinations
            destinations = self.get_user_scan_destinations(user)
            
            for dest in destinations:
                if dest['type'] == 'email':
                    self.send_scan_via_email(user.email, file_path, scan_options)
                elif dest['type'] == 'folder':
                    self.save_scan_to_folder(dest['path'], file_path, user.username)
                elif dest['type'] == 'cloud':
                    self.upload_scan_to_cloud(dest['provider'], file_path, user)
            
            # Log scan job
            scan_job = PrintJob(
                filename=os.path.basename(file_path),
                original_filename=f"Scan from MFP",
                file_path=file_path,
                user_id=user.id,
                status='completed',
                total_pages=1,  # Estimate based on file
                created_at=datetime.utcnow()
            )
            
            db.session.add(scan_job)
            db.session.commit()
            
        except Exception as e:
            print(f"Error processing scan: {e}")
    
    def apply_ocr(self, file_path):
        """Apply OCR to scanned document using Tesseract"""
        try:
            import pytesseract
            from PIL import Image
            import fitz  # PyMuPDF
            
            if file_path.lower().endswith('.pdf'):
                # Extract images from PDF and apply OCR
                doc = fitz.open(file_path)
                ocr_text = ""
                
                for page_num in range(doc.page_count):
                    page = doc[page_num]
                    pix = page.get_pixmap()
                    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                    
                    # Apply OCR
                    page_text = pytesseract.image_to_string(img)
                    ocr_text += f"Page {page_num + 1}:\n{page_text}\n\n"
                
                # Save OCR text alongside PDF
                text_file = file_path.replace('.pdf', '_ocr.txt')
                with open(text_file, 'w', encoding='utf-8') as f:
                    f.write(ocr_text)
                
                doc.close()
            
        except ImportError:
            print("OCR libraries not installed. Install pytesseract and PyMuPDF for OCR support.")
        except Exception as e:
            print(f"OCR processing error: {e}")
    
    def send_scan_via_email(self, email, file_path, scan_options):
        """Send scanned document via email"""
        try:
            msg = MIMEMultipart()
            msg['From'] = 'scanner@company.com'
            msg['To'] = email
            msg['Subject'] = f"Scanned Document - {datetime.now().strftime('%Y-%m-%d %H:%M')}"
            
            # Attach scanned file
            with open(file_path, 'rb') as attachment:
                part = MIMEBase('application', 'octet-stream')
                part.set_payload(attachment.read())
                encoders.encode_base64(part)
                part.add_header(
                    'Content-Disposition',
                    f'attachment; filename= {os.path.basename(file_path)}'
                )
                msg.attach(part)
            
            # Send email
            if self.email_config:
                server = smtplib.SMTP(self.email_config['smtp_server'], self.email_config['smtp_port'])
                if self.email_config['use_tls']:
                    server.starttls()
                server.login(self.email_config['username'], self.email_config['password'])
                server.send_message(msg)
                server.quit()
                
                print(f"Scan emailed to {email}")
                
        except Exception as e:
            print(f"Error sending scan email: {e}")
    
    def save_scan_to_folder(self, destination_path, file_path, username):
        """Save scan to network folder"""
        try:
            # Create user-specific folder
            user_folder = os.path.join(destination_path, username)
            os.makedirs(user_folder, exist_ok=True)
            
            # Copy file to destination
            filename = os.path.basename(file_path)
            dest_file = os.path.join(user_folder, filename)
            
            with open(file_path, 'rb') as src, open(dest_file, 'wb') as dst:
                dst.write(src.read())
            
            print(f"Scan saved to {dest_file}")
            
        except Exception as e:
            print(f"Error saving scan to folder: {e}")
    
    def get_user_scan_destinations(self, user):
        """Get configured scan destinations for user"""
        return [
            {'type': 'email', 'address': user.email},
            {'type': 'folder', 'path': f'/scans/{user.username}/'}
        ]

# Usage example
if __name__ == "__main__":
    mfp_integration = MFPScanIntegration()
    
    # Setup email configuration
    smtp_config = {
        'server': 'smtp.company.com',
        'port': 587,
        'username': 'scanner@company.com',
        'password': 'your-password',
        'use_tls': True
    }
    
    # Configure scan-to-email
    user_aliases = mfp_integration.setup_scan_to_email(smtp_config)
    print("Email aliases configured:")
    print(json.dumps(user_aliases, indent=2))
    
    # Start scan web service
    mfp_integration.start_scan_web_service()
    
    # Get MFP configurations
    mfp_configs = mfp_integration.setup_mfp_configurations()
    print("\nMFP Configuration files:")
    for brand, config in mfp_configs.items():
        print(f"\n{brand.upper()} Configuration:")
        print(json.dumps(config, indent=2))