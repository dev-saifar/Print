"""
Secure Printing (Follow-Me Printing) Implementation
Handles secure print release, authentication, and job management
"""

import hashlib
import secrets
import json
import qrcode
from datetime import datetime, timedelta
from cryptography.fernet import Fernet
from app import db
from app.models import PrintJob, User, Printer

class SecurePrintingSystem:
    """Implements secure printing with multiple authentication methods"""
    
    def __init__(self):
        self.encryption_key = Fernet.generate_key()
        self.cipher = Fernet(self.encryption_key)
        self.active_sessions = {}
        self.print_codes = {}
        
    def submit_secure_print(self, user_id, file_path, print_options):
        """Submit a print job for secure holding"""
        try:
            user = User.query.get(user_id)
            if not user:
                raise ValueError("Invalid user")
            
            # Generate secure print code
            print_code = self.generate_print_code()
            
            # Encrypt the print job data
            job_data = {
                'file_path': file_path,
                'print_options': print_options,
                'user_id': user_id,
                'timestamp': datetime.utcnow().isoformat()
            }
            
            encrypted_data = self.cipher.encrypt(json.dumps(job_data).encode())
            
            # Create print job in held state
            print_job = PrintJob(
                filename=f"secure_{print_code}_{user.username}",
                original_filename=print_options.get('filename', 'Secure Document'),
                file_path=file_path,
                user_id=user_id,
                status='held_secure',
                total_pages=print_options.get('pages', 1),
                copies=print_options.get('copies', 1),
                color_mode=print_options.get('color_mode', 'bw'),
                duplex=print_options.get('duplex', False),
                paper_size=print_options.get('paper_size', 'A4'),
                created_at=datetime.utcnow()
            )
            
            db.session.add(print_job)
            db.session.commit()
            
            # Store encrypted job data with print code
            self.print_codes[print_code] = {
                'job_id': print_job.id,
                'encrypted_data': encrypted_data,
                'user_id': user_id,
                'expires_at': datetime.utcnow() + timedelta(hours=24),
                'attempts': 0
            }
            
            return {
                'print_code': print_code,
                'job_id': print_job.id,
                'qr_code': self.generate_qr_code(print_code, user.username),
                'expires_at': self.print_codes[print_code]['expires_at']
            }
            
        except Exception as e:
            raise Exception(f"Error submitting secure print: {e}")
    
    def authenticate_and_release(self, printer_id, auth_method, auth_data):
        """Authenticate user and release print jobs"""
        try:
            printer = Printer.query.get(printer_id)
            if not printer or not printer.is_active:
                return {'success': False, 'error': 'Printer not available'}
            
            # Authenticate user based on method
            user = None
            if auth_method == 'card':
                user = self.authenticate_card(auth_data.get('card_id'))
            elif auth_method == 'pin':
                user = self.authenticate_pin(auth_data.get('username'), auth_data.get('pin'))
            elif auth_method == 'print_code':
                user = self.authenticate_print_code(auth_data.get('print_code'))
            elif auth_method == 'biometric':
                user = self.authenticate_biometric(auth_data.get('biometric_data'))
            elif auth_method == 'badge':
                user = self.authenticate_badge(auth_data.get('badge_id'))
            
            if not user:
                return {'success': False, 'error': 'Authentication failed'}
            
            # Get user's held print jobs
            held_jobs = PrintJob.query.filter_by(
                user_id=user.id,
                status='held_secure'
            ).all()
            
            if not held_jobs:
                return {'success': False, 'error': 'No print jobs found'}
            
            # Return job selection interface
            return {
                'success': True,
                'user': user.username,
                'jobs': [{
                    'id': job.id,
                    'filename': job.original_filename,
                    'pages': job.total_pages,
                    'copies': job.copies,
                    'color_mode': job.color_mode,
                    'created_at': job.created_at.strftime('%Y-%m-%d %H:%M')
                } for job in held_jobs],
                'session_token': self.create_session_token(user.id, printer_id)
            }
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def release_selected_jobs(self, session_token, selected_job_ids):
        """Release selected print jobs for printing"""
        try:
            session = self.validate_session_token(session_token)
            if not session:
                return {'success': False, 'error': 'Invalid session'}
            
            user_id = session['user_id']
            printer_id = session['printer_id']
            
            released_jobs = []
            for job_id in selected_job_ids:
                job = PrintJob.query.filter_by(
                    id=job_id,
                    user_id=user_id,
                    status='held_secure'
                ).first()
                
                if job:
                    # Release job for printing
                    job.status = 'printing'
                    job.printer_id = printer_id
                    job.started_at = datetime.utcnow()
                    
                    # Calculate and charge cost
                    job.total_cost = job.calculate_cost()
                    
                    released_jobs.append({
                        'id': job.id,
                        'filename': job.original_filename,
                        'cost': job.total_cost
                    })
            
            db.session.commit()
            
            # Clean up session
            if session_token in self.active_sessions:
                del self.active_sessions[session_token]
            
            return {
                'success': True,
                'released_jobs': released_jobs,
                'total_cost': sum(job['cost'] for job in released_jobs)
            }
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def generate_print_code(self):
        """Generate a secure 6-digit print code"""
        return ''.join([str(secrets.randbelow(10)) for _ in range(6)])
    
    def generate_qr_code(self, print_code, username):
        """Generate QR code for print code"""
        qr_data = {
            'type': 'secure_print',
            'code': print_code,
            'user': username,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(json.dumps(qr_data))
        qr.make(fit=True)
        
        # In production, save QR code image and return path
        return f"data:text/plain;base64,{json.dumps(qr_data)}"
    
    def authenticate_card(self, card_id):
        """Authenticate using ID card/badge"""
        try:
            # Hash card ID for security
            card_hash = hashlib.sha256(card_id.encode()).hexdigest()
            
            # Look up user by card hash (in production, store hashed card IDs)
            user = User.query.filter_by(username=card_id).first()  # Simplified
            return user
        except:
            return None
    
    def authenticate_pin(self, username, pin):
        """Authenticate using username and PIN"""
        try:
            user = User.query.filter_by(username=username).first()
            if user and self.verify_pin(user, pin):
                return user
        except:
            return None
    
    def authenticate_print_code(self, print_code):
        """Authenticate using print code"""
        try:
            code_data = self.print_codes.get(print_code)
            if not code_data:
                return None
            
            # Check expiration
            if datetime.utcnow() > code_data['expires_at']:
                del self.print_codes[print_code]
                return None
            
            # Check attempt limit
            if code_data['attempts'] >= 3:
                del self.print_codes[print_code]
                return None
            
            code_data['attempts'] += 1
            user = User.query.get(code_data['user_id'])
            return user
        except:
            return None
    
    def authenticate_biometric(self, biometric_data):
        """Authenticate using biometric data (fingerprint, etc.)"""
        try:
            # In production, implement proper biometric matching
            # This is a placeholder implementation
            user_id = biometric_data.get('user_id')  # Simplified
            return User.query.get(user_id)
        except:
            return None
    
    def authenticate_badge(self, badge_id):
        """Authenticate using proximity badge/RFID"""
        try:
            # Look up user by badge ID
            user = User.query.filter_by(username=badge_id).first()  # Simplified
            return user
        except:
            return None
    
    def verify_pin(self, user, pin):
        """Verify user PIN (in production, use proper hashing)"""
        # This is a placeholder - implement proper PIN storage and verification
        return pin == "1234"  # Simplified
    
    def create_session_token(self, user_id, printer_id):
        """Create temporary session token for print release"""
        token = secrets.token_urlsafe(32)
        self.active_sessions[token] = {
            'user_id': user_id,
            'printer_id': printer_id,
            'created_at': datetime.utcnow(),
            'expires_at': datetime.utcnow() + timedelta(minutes=5)
        }
        return token
    
    def validate_session_token(self, token):
        """Validate session token"""
        session = self.active_sessions.get(token)
        if not session:
            return None
        
        if datetime.utcnow() > session['expires_at']:
            del self.active_sessions[token]
            return None
        
        return session
    
    def setup_printer_authentication_panel(self, printer_id):
        """Generate configuration for printer authentication panel"""
        printer = Printer.query.get(printer_id)
        if not printer:
            return None
        
        panel_config = {
            'printer_id': printer_id,
            'printer_name': printer.name,
            'authentication_methods': [
                {
                    'type': 'card',
                    'name': 'ID Card',
                    'icon': 'card',
                    'enabled': True,
                    'description': 'Tap your ID card'
                },
                {
                    'type': 'pin',
                    'name': 'Username + PIN',
                    'icon': 'keypad',
                    'enabled': True,
                    'description': 'Enter username and PIN'
                },
                {
                    'type': 'print_code',
                    'name': 'Print Code',
                    'icon': 'code',
                    'enabled': True,
                    'description': 'Enter 6-digit print code'
                },
                {
                    'type': 'badge',
                    'name': 'Proximity Badge',
                    'icon': 'badge',
                    'enabled': True,
                    'description': 'Hold badge near reader'
                }
            ],
            'ui_config': {
                'theme': 'corporate',
                'language': 'en',
                'timeout_seconds': 30,
                'show_cost_preview': True,
                'show_environmental_impact': True
            },
            'api_endpoints': {
                'authenticate': f'/api/secure-print/authenticate/{printer_id}',
                'release_jobs': f'/api/secure-print/release/{printer_id}',
                'get_jobs': f'/api/secure-print/jobs/{printer_id}'
            }
        }
        
        return panel_config
    
    def get_security_audit_log(self, start_date=None, end_date=None):
        """Generate security audit log for secure printing"""
        try:
            query = PrintJob.query.filter_by(status='held_secure')
            
            if start_date:
                query = query.filter(PrintJob.created_at >= start_date)
            if end_date:
                query = query.filter(PrintJob.created_at <= end_date)
            
            jobs = query.all()
            
            audit_log = []
            for job in jobs:
                audit_log.append({
                    'job_id': job.id,
                    'user': job.user.username,
                    'created_at': job.created_at.isoformat(),
                    'status': job.status,
                    'printer': job.printer_name if job.printer_name else 'Not assigned',
                    'pages': job.total_pages,
                    'cost': job.total_cost,
                    'security_level': 'secure_hold'
                })
            
            return {
                'audit_log': audit_log,
                'summary': {
                    'total_jobs': len(audit_log),
                    'total_pages': sum(job['pages'] for job in audit_log),
                    'total_cost': sum(job['cost'] or 0 for job in audit_log)
                }
            }
            
        except Exception as e:
            return {'error': str(e)}

# Usage example and API endpoints
def create_secure_printing_api_routes():
    """Create Flask API routes for secure printing"""
    from flask import Blueprint, request, jsonify
    
    secure_api = Blueprint('secure_print', __name__)
    secure_system = SecurePrintingSystem()
    
    @secure_api.route('/api/secure-print/submit', methods=['POST'])
    def submit_secure_print():
        try:
            data = request.json
            result = secure_system.submit_secure_print(
                user_id=data['user_id'],
                file_path=data['file_path'],
                print_options=data['print_options']
            )
            return jsonify(result)
        except Exception as e:
            return jsonify({'error': str(e)}), 400
    
    @secure_api.route('/api/secure-print/authenticate/<int:printer_id>', methods=['POST'])
    def authenticate_for_printing(printer_id):
        try:
            data = request.json
            result = secure_system.authenticate_and_release(
                printer_id=printer_id,
                auth_method=data['auth_method'],
                auth_data=data['auth_data']
            )
            return jsonify(result)
        except Exception as e:
            return jsonify({'error': str(e)}), 400
    
    @secure_api.route('/api/secure-print/release/<int:printer_id>', methods=['POST'])
    def release_print_jobs(printer_id):
        try:
            data = request.json
            result = secure_system.release_selected_jobs(
                session_token=data['session_token'],
                selected_job_ids=data['selected_job_ids']
            )
            return jsonify(result)
        except Exception as e:
            return jsonify({'error': str(e)}), 400
    
    @secure_api.route('/api/secure-print/panel-config/<int:printer_id>')
    def get_panel_config(printer_id):
        try:
            config = secure_system.setup_printer_authentication_panel(printer_id)
            return jsonify(config)
        except Exception as e:
            return jsonify({'error': str(e)}), 400
    
    return secure_api

# Example usage
if __name__ == "__main__":
    secure_system = SecurePrintingSystem()
    
    # Example: Submit a secure print job
    print_result = secure_system.submit_secure_print(
        user_id=1,
        file_path="/uploads/confidential_document.pdf",
        print_options={
            'filename': 'Confidential Report.pdf',
            'pages': 10,
            'copies': 1,
            'color_mode': 'bw',
            'duplex': True
        }
    )
    
    print("Secure print submission:")
    print(json.dumps(print_result, indent=2, default=str))
    
    # Example: Generate printer panel config
    panel_config = secure_system.setup_printer_authentication_panel(1)
    print("\nPrinter authentication panel config:")
    print(json.dumps(panel_config, indent=2))