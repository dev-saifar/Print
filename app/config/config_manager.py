"""
Configuration Manager for Biztra Print Management System
Handles system settings, pricing, and policies
"""
import os
from datetime import datetime
from flask import current_app
from .. import db
from ..models import SystemSettings, PriceList, PrintPolicy

class ConfigManager:
    """Centralized configuration management"""
    
    @staticmethod
    def get_setting(key, default=None):
        """Get system setting value"""
        setting = SystemSettings.query.filter_by(key=key).first()
        if setting:
            return setting.value
        return default
    
    @staticmethod
    def set_setting(key, value, description=None):
        """Set system setting value"""
        setting = SystemSettings.query.filter_by(key=key).first()
        if setting:
            setting.value = str(value)
            setting.updated_at = datetime.utcnow()
        else:
            setting = SystemSettings(
                key=key,
                value=str(value),
                description=description or f"System setting: {key}"
            )
            db.session.add(setting)
        
        db.session.commit()
        return setting
    
    @staticmethod
    def get_pricing_config():
        """Get current pricing configuration"""
        return {
            'cost_per_page_bw': float(ConfigManager.get_setting('cost_per_page_bw', 0.05)),
            'cost_per_page_color': float(ConfigManager.get_setting('cost_per_page_color', 0.15)),
            'cost_per_page_duplex': float(ConfigManager.get_setting('cost_per_page_duplex', 0.04)),
            'currency': ConfigManager.get_setting('currency', 'USD'),
            'tax_rate': float(ConfigManager.get_setting('tax_rate', 0.0))
        }
    
    @staticmethod
    def update_pricing_config(config):
        """Update pricing configuration"""
        for key, value in config.items():
            ConfigManager.set_setting(key, value, f"Pricing configuration: {key}")
    
    @staticmethod
    def get_quota_config():
        """Get quota configuration"""
        return {
            'default_quota_limit': int(ConfigManager.get_setting('default_quota_limit', 1000)),
            'quota_reset_day': int(ConfigManager.get_setting('quota_reset_day', 1)),
            'quota_warning_threshold': float(ConfigManager.get_setting('quota_warning_threshold', 0.8)),
            'enforce_quotas': ConfigManager.get_setting('enforce_quotas', 'true').lower() == 'true'
        }
    
    @staticmethod
    def get_email_config():
        """Get email configuration for scan-to-email"""
        return {
            'smtp_server': ConfigManager.get_setting('smtp_server', 'localhost'),
            'smtp_port': int(ConfigManager.get_setting('smtp_port', 587)),
            'smtp_username': ConfigManager.get_setting('smtp_username', ''),
            'smtp_password': ConfigManager.get_setting('smtp_password', ''),
            'smtp_use_tls': ConfigManager.get_setting('smtp_use_tls', 'true').lower() == 'true',
            'sender_email': ConfigManager.get_setting('sender_email', 'noreply@biztra.com'),
            'sender_name': ConfigManager.get_setting('sender_name', 'Biztra Print Management')
        }
    
    @staticmethod
    def get_scan_config():
        """Get scanning configuration"""
        return {
            'default_resolution': int(ConfigManager.get_setting('default_resolution', 300)),
            'max_resolution': int(ConfigManager.get_setting('max_resolution', 600)),
            'default_format': ConfigManager.get_setting('default_format', 'pdf'),
            'allowed_formats': ConfigManager.get_setting('allowed_formats', 'pdf,jpeg,png,tiff').split(','),
            'scan_folder_base': ConfigManager.get_setting('scan_folder_base', '/scans'),
            'auto_ocr': ConfigManager.get_setting('auto_ocr', 'false').lower() == 'true'
        }
    
    @staticmethod
    def get_printer_config():
        """Get printer configuration"""
        return {
            'default_color_mode': ConfigManager.get_setting('default_color_mode', 'bw'),
            'default_duplex': ConfigManager.get_setting('default_duplex', 'false').lower() == 'true',
            'default_paper_size': ConfigManager.get_setting('default_paper_size', 'A4'),
            'max_copies_per_job': int(ConfigManager.get_setting('max_copies_per_job', 100)),
            'max_pages_per_job': int(ConfigManager.get_setting('max_pages_per_job', 1000)),
            'allow_color_override': ConfigManager.get_setting('allow_color_override', 'true').lower() == 'true'
        }
    
    @staticmethod
    def get_security_config():
        """Get security configuration"""
        return {
            'require_authentication': ConfigManager.get_setting('require_authentication', 'true').lower() == 'true',
            'session_timeout': int(ConfigManager.get_setting('session_timeout', 1800)),
            'max_login_attempts': int(ConfigManager.get_setting('max_login_attempts', 5)),
            'password_min_length': int(ConfigManager.get_setting('password_min_length', 6)),
            'enable_print_codes': ConfigManager.get_setting('enable_print_codes', 'true').lower() == 'true',
            'print_code_expiry': int(ConfigManager.get_setting('print_code_expiry', 86400))  # 24 hours
        }
    
    @staticmethod
    def initialize_default_settings():
        """Initialize system with default settings"""
        defaults = {
            # Pricing
            'cost_per_page_bw': '0.05',
            'cost_per_page_color': '0.15', 
            'cost_per_page_duplex': '0.04',
            'currency': 'USD',
            'tax_rate': '0.0',
            
            # Quotas
            'default_quota_limit': '1000',
            'quota_reset_day': '1',
            'quota_warning_threshold': '0.8',
            'enforce_quotas': 'true',
            
            # Email
            'smtp_server': 'localhost',
            'smtp_port': '587',
            'smtp_use_tls': 'true',
            'sender_email': 'noreply@biztra.com',
            'sender_name': 'Biztra Print Management',
            
            # Scanning
            'default_resolution': '300',
            'max_resolution': '600',
            'default_format': 'pdf',
            'allowed_formats': 'pdf,jpeg,png,tiff',
            'scan_folder_base': '/scans',
            'auto_ocr': 'false',
            
            # Printing
            'default_color_mode': 'bw',
            'default_duplex': 'false',
            'default_paper_size': 'A4',
            'max_copies_per_job': '100',
            'max_pages_per_job': '1000',
            'allow_color_override': 'true',
            
            # Security
            'require_authentication': 'true',
            'session_timeout': '1800',
            'max_login_attempts': '5',
            'password_min_length': '6',
            'enable_print_codes': 'true',
            'print_code_expiry': '86400',
            
            # System
            'system_name': 'Biztra Print Management',
            'company_name': 'Your Company',
            'support_email': 'support@company.com',
            'support_phone': 'ext. 2345',
            'timezone': 'UTC',
            'date_format': '%Y-%m-%d',
            'time_format': '%H:%M:%S'
        }
        
        for key, value in defaults.items():
            existing = SystemSettings.query.filter_by(key=key).first()
            if not existing:
                setting = SystemSettings(
                    key=key,
                    value=value,
                    description=f"Default system setting: {key}"
                )
                db.session.add(setting)
        
        db.session.commit()
    
    @staticmethod
    def export_configuration():
        """Export all configuration to dictionary"""
        settings = SystemSettings.query.all()
        return {
            'settings': {s.key: s.value for s in settings},
            'pricing': ConfigManager.get_pricing_config(),
            'quotas': ConfigManager.get_quota_config(),
            'email': ConfigManager.get_email_config(),
            'scanning': ConfigManager.get_scan_config(),
            'printing': ConfigManager.get_printer_config(),
            'security': ConfigManager.get_security_config(),
            'exported_at': datetime.utcnow().isoformat()
        }
    
    @staticmethod
    def import_configuration(config_data):
        """Import configuration from dictionary"""
        if 'settings' in config_data:
            for key, value in config_data['settings'].items():
                ConfigManager.set_setting(key, value)
        
        return True

class MigrationManager:
    """Handle database migrations and updates"""
    
    @staticmethod
    def get_current_version():
        """Get current database schema version"""
        return ConfigManager.get_setting('schema_version', '1.0.0')
    
    @staticmethod
    def set_version(version):
        """Set database schema version"""
        ConfigManager.set_setting('schema_version', version, 'Database schema version')
    
    @staticmethod
    def needs_migration():
        """Check if migration is needed"""
        current = MigrationManager.get_current_version()
        target = '2.0.0'  # Target version with new features
        return current != target
    
    @staticmethod
    def run_migrations():
        """Run pending migrations"""
        current = MigrationManager.get_current_version()
        
        if current == '1.0.0':
            MigrationManager._migrate_to_1_1_0()
            current = '1.1.0'
        
        if current == '1.1.0':
            MigrationManager._migrate_to_2_0_0()
            current = '2.0.0'
        
        MigrationManager.set_version(current)
        return True
    
    @staticmethod
    def _migrate_to_1_1_0():
        """Migration to version 1.1.0 - Add pricing tables"""
        try:
            # Create default pricing if it doesn't exist
            if not PriceList.query.filter_by(is_default=True).first():
                default_pricing = PriceList(
                    name="Default Pricing",
                    description="System default pricing",
                    cost_per_page_bw=0.05,
                    cost_per_page_color=0.15,
                    cost_per_page_duplex=0.04,
                    is_default=True
                )
                db.session.add(default_pricing)
            
            db.session.commit()
            print("Migration to 1.1.0 completed: Added pricing system")
            
        except Exception as e:
            db.session.rollback()
            print(f"Migration to 1.1.0 failed: {e}")
            raise
    
    @staticmethod
    def _migrate_to_2_0_0():
        """Migration to version 2.0.0 - Add scanning and mobile features"""
        try:
            # Initialize default settings
            ConfigManager.initialize_default_settings()
            
            # Create scanning folder structure
            scan_base = ConfigManager.get_setting('scan_folder_base', '/scans')
            scan_dirs = ['users', 'department', 'shared', 'archive']
            
            for dir_name in scan_dirs:
                full_path = os.path.join(current_app.config['UPLOAD_FOLDER'], 'scans', dir_name)
                os.makedirs(full_path, exist_ok=True)
            
            db.session.commit()
            print("Migration to 2.0.0 completed: Added scanning and mobile features")
            
        except Exception as e:
            db.session.rollback()
            print(f"Migration to 2.0.0 failed: {e}")
            raise