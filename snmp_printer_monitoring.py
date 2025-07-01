"""
SNMP Printer Monitoring Module
Retrieves real-time printer status, alerts, counters, and supplies information
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum
import socket
import struct

# SNMP OIDs for standard printer information
PRINTER_SNMP_OIDS = {
    # Device Information
    'device_description': '1.3.6.1.2.1.1.1.0',
    'device_name': '1.3.6.1.2.1.1.5.0',
    'device_location': '1.3.6.1.2.1.1.6.0',
    'device_contact': '1.3.6.1.2.1.1.4.0',
    'device_uptime': '1.3.6.1.2.1.1.3.0',
    
    # Printer Status
    'printer_status': '1.3.6.1.2.1.25.3.2.1.5.1',
    'printer_detailed_status': '1.3.6.1.2.1.25.3.5.1.1.1',
    
    # Page Counters
    'total_pages': '1.3.6.1.2.1.43.10.2.1.4.1.1',
    'color_pages': '1.3.6.1.2.1.43.10.2.1.4.1.2',
    'duplex_pages': '1.3.6.1.2.1.43.10.2.1.4.1.3',
    'large_pages': '1.3.6.1.2.1.43.10.2.1.4.1.4',
    
    # Supply Levels (Toner/Ink)
    'supply_index': '1.3.6.1.2.1.43.11.1.1.1',
    'supply_description': '1.3.6.1.2.1.43.11.1.1.6',
    'supply_level': '1.3.6.1.2.1.43.11.1.1.9',
    'supply_max_capacity': '1.3.6.1.2.1.43.11.1.1.8',
    'supply_type': '1.3.6.1.2.1.43.11.1.1.4',
    
    # Paper Trays
    'input_index': '1.3.6.1.2.1.43.8.2.1.1',
    'input_type': '1.3.6.1.2.1.43.8.2.1.2',
    'input_capacity': '1.3.6.1.2.1.43.8.2.1.9',
    'input_current_level': '1.3.6.1.2.1.43.8.2.1.10',
    'input_media_name': '1.3.6.1.2.1.43.8.2.1.13',
    
    # Output Trays
    'output_index': '1.3.6.1.2.1.43.9.2.1.1',
    'output_capacity': '1.3.6.1.2.1.43.9.2.1.8',
    'output_remaining': '1.3.6.1.2.1.43.9.2.1.9',
    
    # Error Information
    'console_display_buffer': '1.3.6.1.2.1.43.16.5.1.2.1.1',
    'console_lights': '1.3.6.1.2.1.43.17.6.1.5.1.1',
    
    # Network Information
    'network_interface_index': '1.3.6.1.2.1.2.2.1.1',
    'network_interface_desc': '1.3.6.1.2.1.2.2.1.2',
    'network_interface_speed': '1.3.6.1.2.1.2.2.1.5',
    'network_interface_status': '1.3.6.1.2.1.2.2.1.8',
    
    # Alerts and Events
    'alert_index': '1.3.6.1.2.1.43.18.1.1.1',
    'alert_severity': '1.3.6.1.2.1.43.18.1.1.2',
    'alert_group': '1.3.6.1.2.1.43.18.1.1.3',
    'alert_location': '1.3.6.1.2.1.43.18.1.1.4',
    'alert_code': '1.3.6.1.2.1.43.18.1.1.5',
    'alert_description': '1.3.6.1.2.1.43.18.1.1.6',
    'alert_time': '1.3.6.1.2.1.43.18.1.1.7'
}

# Vendor-specific OIDs
VENDOR_OIDS = {
    'hp': {
        'model': '1.3.6.1.4.1.11.2.3.9.4.2.1.1.3.3.0',
        'serial_number': '1.3.6.1.4.1.11.2.3.9.4.2.1.1.3.3.0',
        'firmware_version': '1.3.6.1.4.1.11.2.3.9.4.2.1.1.3.5.0',
        'total_pages': '1.3.6.1.4.1.11.2.3.9.4.2.1.4.1.2.6.0',
        'duplex_pages': '1.3.6.1.4.1.11.2.3.9.4.2.1.4.1.2.7.0',
        'jam_events': '1.3.6.1.4.1.11.2.3.9.4.2.1.4.1.2.8.0'
    },
    'canon': {
        'model': '1.3.6.1.4.1.1602.1.1.1.1.0',
        'serial_number': '1.3.6.1.4.1.1602.1.1.1.2.0',
        'total_pages': '1.3.6.1.4.1.1602.1.11.1.3.1.4.1.1',
        'color_pages': '1.3.6.1.4.1.1602.1.11.1.3.1.4.1.2',
        'paper_jam_count': '1.3.6.1.4.1.1602.1.11.1.3.1.4.1.301'
    },
    'xerox': {
        'model': '1.3.6.1.4.1.253.8.53.3.2.1.3.1.1',
        'serial_number': '1.3.6.1.4.1.253.8.53.3.2.1.3.1.2',
        'total_impressions': '1.3.6.1.4.1.253.8.53.3.2.1.6.1.20.1',
        'color_impressions': '1.3.6.1.4.1.253.8.53.3.2.1.6.1.20.2',
        'fuser_count': '1.3.6.1.4.1.253.8.53.3.2.1.6.1.20.33'
    },
    'kyocera': {
        'model': '1.3.6.1.4.1.1347.42.2.1.1.1.4.0',
        'serial_number': '1.3.6.1.4.1.1347.42.2.1.1.1.5.0',
        'firmware_version': '1.3.6.1.4.1.1347.42.2.1.1.1.6.0',
        'total_pages': '1.3.6.1.4.1.1347.43.10.1.1.12.1.1',
        'total_copies': '1.3.6.1.4.1.1347.43.10.1.1.12.1.2',
        'total_prints': '1.3.6.1.4.1.1347.43.10.1.1.12.1.3',
        'color_pages': '1.3.6.1.4.1.1347.43.10.1.1.12.1.4',
        'duplex_pages': '1.3.6.1.4.1.1347.43.10.1.1.12.1.5',
        'scan_pages': '1.3.6.1.4.1.1347.43.10.1.1.12.1.6',
        'fax_pages': '1.3.6.1.4.1.1347.43.10.1.1.12.1.7',
        'jam_count': '1.3.6.1.4.1.1347.43.10.1.1.12.1.8',
        'paper_feed_count': '1.3.6.1.4.1.1347.43.10.1.1.12.1.9',
        'drum_count': '1.3.6.1.4.1.1347.43.5.4.2.51.1.0',
        'drum_remaining': '1.3.6.1.4.1.1347.43.5.4.2.51.2.0',
        'toner_black': '1.3.6.1.4.1.1347.43.5.1.1.26.1.2.1',
        'toner_cyan': '1.3.6.1.4.1.1347.43.5.1.1.26.1.2.2',
        'toner_magenta': '1.3.6.1.4.1.1347.43.5.1.1.26.1.2.3',
        'toner_yellow': '1.3.6.1.4.1.1347.43.5.1.1.26.1.2.4',
        'maintenance_count': '1.3.6.1.4.1.1347.43.10.1.1.12.1.10',
        'device_status': '1.3.6.1.4.1.1347.42.2.1.2.1.2.0',
        'engine_status': '1.3.6.1.4.1.1347.42.2.1.2.1.3.0',
        'current_user': '1.3.6.1.4.1.1347.42.2.1.2.1.4.0'
    }
}

class AlertSeverity(Enum):
    OTHER = 1
    CRITICAL = 3
    WARNING = 4
    ADVISORY = 5

class PrinterStatus(Enum):
    OTHER = 1
    UNKNOWN = 2
    IDLE = 3
    PRINTING = 4
    WARMUP = 5

@dataclass
class PrinterAlert:
    index: int
    severity: AlertSeverity
    group: str
    location: str
    code: int
    description: str
    time: datetime

@dataclass
class SupplyInfo:
    index: int
    description: str
    type: str
    level: int
    max_capacity: int
    percentage: float

@dataclass
class PrinterCounters:
    total_pages: int
    color_pages: int
    duplex_pages: int
    large_pages: int
    jam_events: int
    maintenance_count: int

@dataclass
class PrinterInfo:
    ip_address: str
    name: str
    model: str
    serial_number: str
    location: str
    status: PrinterStatus
    uptime: int
    firmware_version: str
    counters: PrinterCounters
    supplies: List[SupplyInfo]
    alerts: List[PrinterAlert]
    last_updated: datetime

class SNMPPrinterMonitor:
    """SNMP-based printer monitoring system"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.monitored_printers = {}
        self.snmp_community = 'public'
        self.snmp_port = 161
        self.timeout = 5
        
    def add_printer(self, ip_address: str, community: str = 'public', vendor: str = 'generic'):
        """Add a printer to monitoring"""
        self.monitored_printers[ip_address] = {
            'community': community,
            'vendor': vendor.lower(),
            'last_check': None,
            'status': 'unknown'
        }
        
    def remove_printer(self, ip_address: str):
        """Remove a printer from monitoring"""
        if ip_address in self.monitored_printers:
            del self.monitored_printers[ip_address]
    
    async def get_printer_info(self, ip_address: str) -> Optional[PrinterInfo]:
        """Get comprehensive printer information via SNMP"""
        try:
            if ip_address not in self.monitored_printers:
                self.logger.warning(f"Printer {ip_address} not in monitoring list")
                return None
            
            printer_config = self.monitored_printers[ip_address]
            community = printer_config['community']
            vendor = printer_config['vendor']
            
            # Basic device information
            device_info = await self._get_device_info(ip_address, community)
            if not device_info:
                return None
            
            # Get printer-specific information
            printer_status = await self._get_printer_status(ip_address, community)
            counters = await self._get_printer_counters(ip_address, community, vendor)
            supplies = await self._get_supply_levels(ip_address, community)
            alerts = await self._get_printer_alerts(ip_address, community)
            
            # Create comprehensive printer info
            printer_info = PrinterInfo(
                ip_address=ip_address,
                name=device_info.get('name', 'Unknown'),
                model=device_info.get('model', 'Unknown'),
                serial_number=device_info.get('serial', 'Unknown'),
                location=device_info.get('location', 'Unknown'),
                status=printer_status,
                uptime=device_info.get('uptime', 0),
                firmware_version=device_info.get('firmware', 'Unknown'),
                counters=counters,
                supplies=supplies,
                alerts=alerts,
                last_updated=datetime.utcnow()
            )
            
            # Update monitoring status
            self.monitored_printers[ip_address]['last_check'] = datetime.utcnow()
            self.monitored_printers[ip_address]['status'] = 'online'
            
            return printer_info
            
        except Exception as e:
            self.logger.error(f"Error getting printer info for {ip_address}: {e}")
            self.monitored_printers[ip_address]['status'] = 'error'
            return None
    
    async def _get_device_info(self, ip_address: str, community: str) -> Dict[str, Any]:
        """Get basic device information"""
        try:
            device_info = {}
            
            # Simulate SNMP GET operations
            # In production, use pysnmp or similar library
            basic_oids = {
                'name': PRINTER_SNMP_OIDS['device_name'],
                'description': PRINTER_SNMP_OIDS['device_description'],
                'location': PRINTER_SNMP_OIDS['device_location'],
                'uptime': PRINTER_SNMP_OIDS['device_uptime']
            }
            
            for key, oid in basic_oids.items():
                try:
                    # Simulate SNMP get
                    value = await self._snmp_get(ip_address, community, oid)
                    device_info[key] = value
                except Exception as e:
                    self.logger.warning(f"Failed to get {key} for {ip_address}: {e}")
                    device_info[key] = 'Unknown'
            
            return device_info
            
        except Exception as e:
            self.logger.error(f"Error getting device info: {e}")
            return {}
    
    async def _get_printer_status(self, ip_address: str, community: str) -> PrinterStatus:
        """Get current printer status"""
        try:
            status_value = await self._snmp_get(ip_address, community, PRINTER_SNMP_OIDS['printer_status'])
            return PrinterStatus(int(status_value)) if status_value else PrinterStatus.UNKNOWN
        except:
            return PrinterStatus.UNKNOWN
    
    async def _get_printer_counters(self, ip_address: str, community: str, vendor: str) -> PrinterCounters:
        """Get printer page counters"""
        try:
            counters = PrinterCounters(
                total_pages=0,
                color_pages=0,
                duplex_pages=0,
                large_pages=0,
                jam_events=0,
                maintenance_count=0
            )
            
            # Try vendor-specific OIDs first
            if vendor in VENDOR_OIDS:
                vendor_oids = VENDOR_OIDS[vendor]
                try:
                    if vendor == 'kyocera':
                        # Kyocera-specific counter handling
                        if 'total_pages' in vendor_oids:
                            counters.total_pages = await self._snmp_get(ip_address, community, vendor_oids['total_pages']) or 0
                        if 'color_pages' in vendor_oids:
                            counters.color_pages = await self._snmp_get(ip_address, community, vendor_oids['color_pages']) or 0
                        if 'duplex_pages' in vendor_oids:
                            counters.duplex_pages = await self._snmp_get(ip_address, community, vendor_oids['duplex_pages']) or 0
                        if 'jam_count' in vendor_oids:
                            counters.jam_events = await self._snmp_get(ip_address, community, vendor_oids['jam_count']) or 0
                        if 'maintenance_count' in vendor_oids:
                            counters.maintenance_count = await self._snmp_get(ip_address, community, vendor_oids['maintenance_count']) or 0
                        
                        # Additional Kyocera counters
                        if 'total_copies' in vendor_oids:
                            total_copies = await self._snmp_get(ip_address, community, vendor_oids['total_copies']) or 0
                            counters.total_pages = max(counters.total_pages, total_copies)
                        if 'total_prints' in vendor_oids:
                            total_prints = await self._snmp_get(ip_address, community, vendor_oids['total_prints']) or 0
                            counters.total_pages = max(counters.total_pages, total_prints)
                    else:
                        # Other vendors
                        if 'total_pages' in vendor_oids:
                            counters.total_pages = await self._snmp_get(ip_address, community, vendor_oids['total_pages']) or 0
                        if 'color_pages' in vendor_oids:
                            counters.color_pages = await self._snmp_get(ip_address, community, vendor_oids['color_pages']) or 0
                        if 'duplex_pages' in vendor_oids:
                            counters.duplex_pages = await self._snmp_get(ip_address, community, vendor_oids['duplex_pages']) or 0
                        if 'jam_events' in vendor_oids:
                            counters.jam_events = await self._snmp_get(ip_address, community, vendor_oids['jam_events']) or 0
                except Exception as e:
                    self.logger.warning(f"Vendor-specific counter retrieval failed: {e}")
            
            # Fallback to standard OIDs
            if counters.total_pages == 0:
                try:
                    counters.total_pages = await self._snmp_get(ip_address, community, PRINTER_SNMP_OIDS['total_pages']) or 0
                    counters.color_pages = await self._snmp_get(ip_address, community, PRINTER_SNMP_OIDS['color_pages']) or 0
                    counters.duplex_pages = await self._snmp_get(ip_address, community, PRINTER_SNMP_OIDS['duplex_pages']) or 0
                except Exception as e:
                    self.logger.warning(f"Standard counter retrieval failed: {e}")
            
            return counters
            
        except Exception as e:
            self.logger.error(f"Error getting printer counters: {e}")
            return PrinterCounters(0, 0, 0, 0, 0, 0)
    
    async def _get_supply_levels(self, ip_address: str, community: str) -> List[SupplyInfo]:
        """Get supply levels (toner, ink, etc.)"""
        try:
            supplies = []
            
            # Check if this is a monitored printer to get vendor info
            printer_config = self.monitored_printers.get(ip_address, {})
            vendor = printer_config.get('vendor', 'generic')
            
            # Try vendor-specific supply monitoring first
            if vendor == 'kyocera' and vendor in VENDOR_OIDS:
                vendor_oids = VENDOR_OIDS[vendor]
                
                # Kyocera-specific toner monitoring
                toner_colors = [
                    ('toner_black', 'Black Toner'),
                    ('toner_cyan', 'Cyan Toner'),
                    ('toner_magenta', 'Magenta Toner'),
                    ('toner_yellow', 'Yellow Toner')
                ]
                
                for toner_oid, description in toner_colors:
                    if toner_oid in vendor_oids:
                        try:
                            level = await self._snmp_get(ip_address, community, vendor_oids[toner_oid])
                            if level is not None:
                                # Kyocera returns percentage directly
                                percentage = int(level)
                                supply = SupplyInfo(
                                    index=len(supplies) + 1,
                                    description=description,
                                    type="Toner",
                                    level=percentage,
                                    max_capacity=100,
                                    percentage=float(percentage)
                                )
                                supplies.append(supply)
                        except Exception as e:
                            self.logger.warning(f"Error getting Kyocera {description}: {e}")
                
                # Kyocera drum monitoring
                if 'drum_remaining' in vendor_oids:
                    try:
                        drum_level = await self._snmp_get(ip_address, community, vendor_oids['drum_remaining'])
                        if drum_level is not None:
                            supply = SupplyInfo(
                                index=len(supplies) + 1,
                                description="Drum Unit",
                                type="Drum",
                                level=int(drum_level),
                                max_capacity=100,
                                percentage=float(drum_level)
                            )
                            supplies.append(supply)
                    except Exception as e:
                        self.logger.warning(f"Error getting Kyocera drum level: {e}")
                
                # If vendor-specific worked, return those results
                if supplies:
                    return supplies
            
            # Fallback to standard SNMP supply monitoring
            supply_indices = await self._snmp_walk(ip_address, community, PRINTER_SNMP_OIDS['supply_index'])
            
            for index in supply_indices:
                try:
                    description = await self._snmp_get(ip_address, community, f"{PRINTER_SNMP_OIDS['supply_description']}.{index}")
                    level = await self._snmp_get(ip_address, community, f"{PRINTER_SNMP_OIDS['supply_level']}.{index}")
                    max_capacity = await self._snmp_get(ip_address, community, f"{PRINTER_SNMP_OIDS['supply_max_capacity']}.{index}")
                    supply_type = await self._snmp_get(ip_address, community, f"{PRINTER_SNMP_OIDS['supply_type']}.{index}")
                    
                    if level is not None and max_capacity is not None and max_capacity > 0:
                        percentage = (int(level) / int(max_capacity)) * 100
                        
                        supply = SupplyInfo(
                            index=int(index),
                            description=str(description) if description else f"Supply {index}",
                            type=str(supply_type) if supply_type else "Unknown",
                            level=int(level),
                            max_capacity=int(max_capacity),
                            percentage=round(percentage, 1)
                        )
                        supplies.append(supply)
                        
                except Exception as e:
                    self.logger.warning(f"Error getting supply {index} info: {e}")
            
            return supplies
            
        except Exception as e:
            self.logger.error(f"Error getting supply levels: {e}")
            return []
    
    async def _get_printer_alerts(self, ip_address: str, community: str) -> List[PrinterAlert]:
        """Get active printer alerts"""
        try:
            alerts = []
            
            # Walk through alert table
            alert_indices = await self._snmp_walk(ip_address, community, PRINTER_SNMP_OIDS['alert_index'])
            
            for index in alert_indices:
                try:
                    severity = await self._snmp_get(ip_address, community, f"{PRINTER_SNMP_OIDS['alert_severity']}.{index}")
                    group = await self._snmp_get(ip_address, community, f"{PRINTER_SNMP_OIDS['alert_group']}.{index}")
                    location = await self._snmp_get(ip_address, community, f"{PRINTER_SNMP_OIDS['alert_location']}.{index}")
                    code = await self._snmp_get(ip_address, community, f"{PRINTER_SNMP_OIDS['alert_code']}.{index}")
                    description = await self._snmp_get(ip_address, community, f"{PRINTER_SNMP_OIDS['alert_description']}.{index}")
                    alert_time = await self._snmp_get(ip_address, community, f"{PRINTER_SNMP_OIDS['alert_time']}.{index}")
                    
                    alert = PrinterAlert(
                        index=int(index),
                        severity=AlertSeverity(int(severity)) if severity else AlertSeverity.OTHER,
                        group=str(group) if group else "Unknown",
                        location=str(location) if location else "Unknown",
                        code=int(code) if code else 0,
                        description=str(description) if description else "Unknown alert",
                        time=datetime.utcnow()  # In production, parse alert_time
                    )
                    alerts.append(alert)
                    
                except Exception as e:
                    self.logger.warning(f"Error getting alert {index} info: {e}")
            
            return alerts
            
        except Exception as e:
            self.logger.error(f"Error getting printer alerts: {e}")
            return []
    
    async def _snmp_get(self, ip_address: str, community: str, oid: str) -> Optional[Any]:
        """Perform SNMP GET operation"""
        try:
            # This is a simplified simulation
            # In production, use pysnmp or similar library
            
            # Simulate network delay
            await asyncio.sleep(0.01)
            
            # Return simulated data based on OID
            if 'device_name' in oid:
                return f"Printer-{ip_address.split('.')[-1]}"
            elif 'total_pages' in oid or '1.3.6.1.4.1.1347.43.10.1.1.12.1.1' in oid:
                return 12500
            elif 'color_pages' in oid or '1.3.6.1.4.1.1347.43.10.1.1.12.1.4' in oid:
                return 3200
            elif 'duplex_pages' in oid or '1.3.6.1.4.1.1347.43.10.1.1.12.1.5' in oid:
                return 8900
            elif 'jam_count' in oid or '1.3.6.1.4.1.1347.43.10.1.1.12.1.8' in oid:
                return 15
            elif 'maintenance_count' in oid or '1.3.6.1.4.1.1347.43.10.1.1.12.1.10' in oid:
                return 3
            elif 'toner_black' in oid or '1.3.6.1.4.1.1347.43.5.1.1.26.1.2.1' in oid:
                return 85  # Kyocera percentage
            elif 'toner_cyan' in oid or '1.3.6.1.4.1.1347.43.5.1.1.26.1.2.2' in oid:
                return 72
            elif 'toner_magenta' in oid or '1.3.6.1.4.1.1347.43.5.1.1.26.1.2.3' in oid:
                return 68
            elif 'toner_yellow' in oid or '1.3.6.1.4.1.1347.43.5.1.1.26.1.2.4' in oid:
                return 91
            elif 'drum_remaining' in oid or '1.3.6.1.4.1.1347.43.5.4.2.51.2.0' in oid:
                return 45  # Drum percentage
            elif 'supply_level' in oid:
                return 85
            elif 'supply_max_capacity' in oid:
                return 100
            elif 'supply_description' in oid:
                return "Black Toner"
            elif 'printer_status' in oid:
                return 3  # Idle
            elif 'model' in oid and '1.3.6.1.4.1.1347' in oid:
                return "ECOSYS M6635cidn"
            elif 'serial_number' in oid and '1.3.6.1.4.1.1347' in oid:
                return "ZKR1234567"
            elif 'firmware_version' in oid and '1.3.6.1.4.1.1347' in oid:
                return "3AY-3700-030"
            else:
                return None
                
        except Exception as e:
            self.logger.error(f"SNMP GET error for {ip_address}:{oid}: {e}")
            return None
    
    async def _snmp_walk(self, ip_address: str, community: str, base_oid: str) -> List[str]:
        """Perform SNMP WALK operation"""
        try:
            # Simulate SNMP walk returning indices
            await asyncio.sleep(0.05)
            return ['1', '2', '3']  # Simulated supply indices
            
        except Exception as e:
            self.logger.error(f"SNMP WALK error for {ip_address}:{base_oid}: {e}")
            return []
    
    async def monitor_all_printers(self) -> Dict[str, Optional[PrinterInfo]]:
        """Monitor all registered printers"""
        results = {}
        
        # Create tasks for concurrent monitoring
        tasks = []
        for ip_address in self.monitored_printers.keys():
            task = asyncio.create_task(self.get_printer_info(ip_address))
            tasks.append((ip_address, task))
        
        # Wait for all tasks to complete
        for ip_address, task in tasks:
            try:
                result = await task
                results[ip_address] = result
            except Exception as e:
                self.logger.error(f"Error monitoring printer {ip_address}: {e}")
                results[ip_address] = None
        
        return results
    
    def get_printer_summary(self, printer_info: PrinterInfo) -> Dict[str, Any]:
        """Generate a summary of printer status"""
        if not printer_info:
            return {'status': 'unavailable'}
        
        # Calculate supply status
        supply_status = 'ok'
        low_supplies = []
        
        for supply in printer_info.supplies:
            if supply.percentage < 10:
                supply_status = 'critical'
                low_supplies.append(supply.description)
            elif supply.percentage < 25 and supply_status == 'ok':
                supply_status = 'warning'
                low_supplies.append(supply.description)
        
        # Check for critical alerts
        critical_alerts = [alert for alert in printer_info.alerts if alert.severity == AlertSeverity.CRITICAL]
        warning_alerts = [alert for alert in printer_info.alerts if alert.severity == AlertSeverity.WARNING]
        
        overall_status = 'online'
        if critical_alerts or supply_status == 'critical':
            overall_status = 'error'
        elif warning_alerts or supply_status == 'warning':
            overall_status = 'warning'
        elif printer_info.status != PrinterStatus.IDLE:
            overall_status = 'busy'
        
        return {
            'status': overall_status,
            'name': printer_info.name,
            'model': printer_info.model,
            'location': printer_info.location,
            'total_pages': printer_info.counters.total_pages,
            'supply_status': supply_status,
            'low_supplies': low_supplies,
            'critical_alerts': len(critical_alerts),
            'warning_alerts': len(warning_alerts),
            'last_updated': printer_info.last_updated.isoformat(),
            'uptime_days': printer_info.uptime // (24 * 60 * 60) if printer_info.uptime else 0
        }

# Integration with Flask application
def create_snmp_monitoring_service():
    """Create SNMP monitoring service for Flask app"""
    monitor = SNMPPrinterMonitor()
    
    async def update_printer_database():
        """Update database with SNMP data"""
        from app import db
        from app.models import Printer
        
        try:
            # Get all printers from database
            printers = Printer.query.filter_by(is_active=True).all()
            
            # Add printers to monitoring
            for printer in printers:
                if printer.ip_address:
                    # Detect vendor from model
                    vendor = 'generic'
                    if printer.model:
                        model_lower = printer.model.lower()
                        if 'hp' in model_lower or 'hewlett' in model_lower:
                            vendor = 'hp'
                        elif 'canon' in model_lower:
                            vendor = 'canon'
                        elif 'xerox' in model_lower:
                            vendor = 'xerox'
                    
                    monitor.add_printer(printer.ip_address, 'public', vendor)
            
            # Monitor all printers
            results = await monitor.monitor_all_printers()
            
            # Update database with results
            for ip_address, printer_info in results.items():
                printer = Printer.query.filter_by(ip_address=ip_address).first()
                if printer and printer_info:
                    # Update printer status
                    if printer_info.status == PrinterStatus.IDLE:
                        printer.status = 'online'
                    elif printer_info.status == PrinterStatus.PRINTING:
                        printer.status = 'printing'
                    else:
                        printer.status = 'offline'
                    
                    # Update counters
                    printer.total_pages_printed = printer_info.counters.total_pages
                    
                    # Update supply levels (use primary supply)
                    if printer_info.supplies:
                        primary_supply = printer_info.supplies[0]
                        printer.toner_level = int(primary_supply.percentage)
                    
                    # Update last seen
                    printer.last_seen = datetime.utcnow()
            
            db.session.commit()
            
        except Exception as e:
            logging.error(f"Error updating printer database: {e}")
    
    return monitor, update_printer_database

# Example usage and testing
if __name__ == "__main__":
    async def main():
        monitor = SNMPPrinterMonitor()
        
        # Add sample printers
        monitor.add_printer('192.168.1.100', 'public', 'hp')
        monitor.add_printer('192.168.1.101', 'public', 'canon')
        monitor.add_printer('192.168.1.102', 'public', 'xerox')
        monitor.add_printer('192.168.1.103', 'public', 'kyocera')
        
        # Monitor all printers
        results = await monitor.monitor_all_printers()
        
        # Display results
        for ip, info in results.items():
            if info:
                print(f"\n=== Printer {ip} ===")
                print(f"Name: {info.name}")
                print(f"Model: {info.model}")
                print(f"Status: {info.status.name}")
                print(f"Total Pages: {info.counters.total_pages:,}")
                print(f"Color Pages: {info.counters.color_pages:,}")
                
                print("\nSupplies:")
                for supply in info.supplies:
                    print(f"  {supply.description}: {supply.percentage}%")
                
                print("\nAlerts:")
                for alert in info.alerts:
                    print(f"  {alert.severity.name}: {alert.description}")
                
                # Generate summary
                summary = monitor.get_printer_summary(info)
                print(f"\nSummary: {json.dumps(summary, indent=2)}")
            else:
                print(f"\n=== Printer {ip} === OFFLINE")
    
    # Run the example
    asyncio.run(main())
