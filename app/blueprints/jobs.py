"""
Print Jobs Management Blueprint
Handles job upload, processing, and release functionality
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta
import os
import uuid

from .. import db, scheduler
from ..models import PrintJob, User, Printer, PrintPolicy
from ..utils import allowed_file, get_file_pages, process_print_job

jobs_bp = Blueprint('jobs', __name__, url_prefix='/jobs')

@jobs_bp.route('/')
@login_required
def list_jobs():
    """Display user's print jobs"""
    page = request.args.get('page', 1, type=int)
    jobs = PrintJob.query.filter_by(user_id=current_user.id)\
                         .order_by(PrintJob.created_at.desc())\
                         .paginate(page=page, per_page=10, error_out=False)
    return render_template('jobs/list.html', jobs=jobs)

@jobs_bp.route('/upload', methods=['GET', 'POST'])
@login_required
def upload():
    """Upload new print job"""
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('No file selected', 'error')
            return redirect(request.url)
        
        file = request.files['file']
        if file.filename == '' or not file:
            flash('No file selected', 'error')
            return redirect(request.url)
        
        if file and allowed_file(file.filename):
            # Secure filename and save
            filename = secure_filename(file.filename or "untitled")
            unique_filename = f"{uuid.uuid4()}_{filename}"
            file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], unique_filename)
            file.save(file_path)
            
            # Get print settings from form
            copies = int(request.form.get('copies', 1))
            color_mode = request.form.get('color_mode', 'bw')
            duplex = request.form.get('duplex') == 'on'
            paper_size = request.form.get('paper_size', 'A4')
            printer_id = request.form.get('printer_id')
            
            # Calculate pages and cost
            total_pages = get_file_pages(file_path)
            
            # Create print job
            print_job = PrintJob(
                filename=unique_filename,
                original_filename=filename,
                file_path=file_path,
                user_id=current_user.id,
                copies=copies,
                color_mode=color_mode,
                duplex=duplex,
                paper_size=paper_size,
                total_pages=total_pages,
                printer_id=printer_id,
                department_id=current_user.department_id
            )
            
            # Calculate cost based on pricing policy
            print_job.calculate_cost()
            
            # Check user quota and balance
            if not current_user.can_print(total_pages * copies, print_job.total_cost):
                flash('Insufficient balance or quota exceeded', 'error')
                os.remove(file_path)  # Clean up file
                return redirect(request.url)
            
            db.session.add(print_job)
            db.session.commit()
            
            # Schedule for processing (hold for release)
            flash(f'Print job uploaded successfully! Cost: ${print_job.total_cost:.2f}', 'success')
            return redirect(url_for('jobs.list_jobs'))
        else:
            flash('Invalid file type. Please upload PDF, DOC, DOCX, or image files.', 'error')
    
    # Get available printers for form
    printers = Printer.query.filter_by(is_active=True).all()
    return render_template('jobs/upload.html', printers=printers)

@jobs_bp.route('/<int:job_id>/preview')
@login_required
def preview_job(job_id):
    """Preview print job before release"""
    job = PrintJob.query.get_or_404(job_id)
    
    # Ensure user owns the job or is admin
    if job.user_id != current_user.id and current_user.role != 'admin':
        flash('Access denied', 'error')
        return redirect(url_for('jobs.list_jobs'))
    
    printers = Printer.query.filter_by(is_active=True).all()
    return render_template('jobs/preview.html', job=job, printers=printers)

@jobs_bp.route('/<int:job_id>/release', methods=['POST'])
@login_required
def release_job(job_id):
    """Release print job for printing"""
    job = PrintJob.query.get_or_404(job_id)
    
    # Ensure user owns the job or is admin
    if job.user_id != current_user.id and current_user.role != 'admin':
        flash('Access denied', 'error')
        return redirect(url_for('jobs.list_jobs'))
    
    if job.status != 'pending':
        flash('Job cannot be released', 'error')
        return redirect(url_for('jobs.list_jobs'))
    
    # Get printer selection
    printer_id = request.form.get('printer_id')
    if printer_id:
        job.printer_id = printer_id
        printer = Printer.query.get(printer_id)
        job.printer_name = printer.name if printer else 'Unknown'
    
    # Update job for printing
    job.status = 'printing'
    job.started_at = datetime.utcnow()
    
    # Deduct cost and quota
    current_user.balance -= job.total_cost
    current_user.quota_used += (job.total_pages * job.copies)
    
    db.session.commit()
    
    # Schedule print processing
    scheduler.add_job(
        func=process_print_job,
        args=[job.id],
        trigger='date',
        run_date=datetime.utcnow() + timedelta(seconds=2),
        id=f'print_job_{job.id}'
    )
    
    flash('Print job released successfully!', 'success')
    return redirect(url_for('jobs.list_jobs'))

@jobs_bp.route('/<int:job_id>/cancel', methods=['POST'])
@login_required
def cancel_job(job_id):
    """Cancel pending print job"""
    job = PrintJob.query.get_or_404(job_id)
    
    # Ensure user owns the job or is admin
    if job.user_id != current_user.id and current_user.role != 'admin':
        flash('Access denied', 'error')
        return redirect(url_for('jobs.list_jobs'))
    
    if job.status != 'pending':
        flash('Job cannot be cancelled', 'error')
        return redirect(url_for('jobs.list_jobs'))
    
    # Clean up file
    if os.path.exists(job.file_path):
        os.remove(job.file_path)
    
    job.status = 'cancelled'
    db.session.commit()
    
    flash('Print job cancelled', 'info')
    return redirect(url_for('jobs.list_jobs'))

@jobs_bp.route('/bulk-release', methods=['POST'])
@login_required
def bulk_release():
    """Release multiple jobs at once"""
    job_ids = request.form.getlist('job_ids')
    printer_id = request.form.get('printer_id')
    
    if not job_ids:
        flash('No jobs selected', 'error')
        return redirect(url_for('jobs.list_jobs'))
    
    released_count = 0
    for job_id in job_ids:
        job = PrintJob.query.get(job_id)
        if job and job.user_id == current_user.id and job.status == 'pending':
            if printer_id:
                job.printer_id = printer_id
                printer = Printer.query.get(printer_id)
                job.printer_name = printer.name if printer else 'Unknown'
            
            job.status = 'printing'
            job.started_at = datetime.utcnow()
            
            # Deduct cost and quota
            current_user.balance -= job.total_cost
            current_user.quota_used += (job.total_pages * job.copies)
            
            # Schedule processing
            scheduler.add_job(
                func=process_print_job,
                args=[job.id],
                trigger='date',
                run_date=datetime.utcnow() + timedelta(seconds=2 + released_count),
                id=f'print_job_{job.id}'
            )
            released_count += 1
    
    db.session.commit()
    flash(f'{released_count} print jobs released successfully!', 'success')
    return redirect(url_for('jobs.list_jobs'))