from flask import render_template, request, jsonify, redirect, url_for, send_file, flash
from app import app, db
from models import ScrapingJob, Product
from scraper import ProductScraper
import threading
import csv
import io
import logging
from datetime import datetime

@app.route('/')
def index():
    """Main page with search form"""
    recent_jobs = ScrapingJob.query.order_by(ScrapingJob.created_at.desc()).limit(10).all()
    return render_template('index.html', recent_jobs=recent_jobs)

@app.route('/search', methods=['POST'])
def start_search():
    """Start a new scraping job"""
    try:
        search_term = request.form.get('search_term', '').strip()
        max_pages = int(request.form.get('max_pages', 3))
        
        if not search_term:
            flash('Please enter a search term', 'error')
            return redirect(url_for('index'))
        
        if max_pages < 1 or max_pages > 10:
            flash('Number of pages must be between 1 and 10', 'error')
            return redirect(url_for('index'))
        
        # Create new scraping job
        job = ScrapingJob(
            search_term=search_term,
            total_pages=max_pages,
            status='pending'
        )
        db.session.add(job)
        db.session.commit()
        
        # Start scraping in background thread
        thread = threading.Thread(
            target=run_scraping_job,
            args=(job.id, search_term, max_pages)
        )
        thread.daemon = True
        thread.start()
        
        flash(f'Scraping job started for "{search_term}"', 'success')
        return redirect(url_for('job_status', job_id=job.id))
        
    except Exception as e:
        logging.error(f"Error starting search: {str(e)}")
        flash('An error occurred while starting the search', 'error')
        return redirect(url_for('index'))

def run_scraping_job(job_id, search_term, max_pages):
    """Run scraping job in background"""
    try:
        with app.app_context():
            scraper = ProductScraper()
            scraper.search_products(search_term, max_pages, job_id)
    except Exception as e:
        logging.error(f"Error in scraping job {job_id}: {str(e)}")
        with app.app_context():
            job = ScrapingJob.query.get(job_id)
            if job:
                job.status = 'failed'
                job.error_message = str(e)
                job.completed_at = datetime.utcnow()
                db.session.commit()

@app.route('/job/<int:job_id>')
def job_status(job_id):
    """View job status and results"""
    job = ScrapingJob.query.get_or_404(job_id)
    products = Product.query.filter_by(job_id=job_id).all()
    return render_template('results.html', job=job, products=products)

@app.route('/api/job/<int:job_id>/status')
def api_job_status(job_id):
    """API endpoint for job status"""
    job = ScrapingJob.query.get_or_404(job_id)
    return jsonify(job.to_dict())

@app.route('/job/<int:job_id>/export')
def export_csv(job_id):
    """Export job results to CSV"""
    try:
        job = ScrapingJob.query.get_or_404(job_id)
        products = Product.query.filter_by(job_id=job_id).all()
        
        if not products:
            flash('No products found to export', 'warning')
            return redirect(url_for('job_status', job_id=job_id))
        
        # Create CSV in memory
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write header
        headers = [
            'Title', 'Price', 'Original Price', 'Rating', 'Review Count',
            'Seller Name', 'Product URL', 'Image URL', 'Shipping Info',
            'Discount Percentage', 'Scraped At'
        ]
        writer.writerow(headers)
        
        # Write data
        for product in products:
            row = [
                product.title,
                product.price,
                product.original_price,
                product.rating,
                product.review_count,
                product.seller_name,
                product.product_url,
                product.image_url,
                product.shipping_info,
                product.discount_percentage,
                product.created_at.strftime('%Y-%m-%d %H:%M:%S') if product.created_at else ''
            ]
            writer.writerow(row)
        
        # Prepare file for download
        output.seek(0)
        file_data = io.BytesIO()
        file_data.write(output.getvalue().encode('utf-8'))
        file_data.seek(0)
        
        filename = f"aliexpress_{job.search_term.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        
        return send_file(
            file_data,
            mimetype='text/csv',
            as_attachment=True,
            download_name=filename
        )
        
    except Exception as e:
        logging.error(f"Error exporting CSV: {str(e)}")
        flash('An error occurred while exporting data', 'error')
        return redirect(url_for('job_status', job_id=job_id))

@app.route('/job/<int:job_id>/delete', methods=['POST'])
def delete_job(job_id):
    """Delete a scraping job and its products"""
    try:
        job = ScrapingJob.query.get_or_404(job_id)
        db.session.delete(job)
        db.session.commit()
        flash('Job deleted successfully', 'success')
    except Exception as e:
        logging.error(f"Error deleting job: {str(e)}")
        flash('An error occurred while deleting the job', 'error')
    
    return redirect(url_for('index'))

@app.route('/api/products/<int:job_id>')
def api_products(job_id):
    """API endpoint for products"""
    products = Product.query.filter_by(job_id=job_id).all()
    return jsonify([product.to_dict() for product in products])

@app.errorhandler(404)
def not_found_error(error):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return render_template('500.html'), 500
@app.route('/api/search', methods=['POST'])
def api_search():
    """API to trigger a scraping job from Make.com or other services"""
    try:
        data = request.get_json()
        search_term = data.get('query', '').strip()
        max_pages = int(data.get('max_pages', 3))

        if not search_term:
            return jsonify({'error': 'Missing search query'}), 400

        if max_pages < 1 or max_pages > 10:
            return jsonify({'error': 'max_pages must be between 1 and 10'}), 400

        # Create scraping job
        job = ScrapingJob(
            search_term=search_term,
            total_pages=max_pages,
            status='pending'
        )
        db.session.add(job)
        db.session.commit()

        # Run job in background
        thread = threading.Thread(
            target=run_scraping_job,
            args=(job.id, search_term, max_pages)
        )
        thread.daemon = True
        thread.start()

        return jsonify({
            'message': f'Scraping started for "{search_term}"',
            'job_id': job.id,
            'status_url': f'/api/job/{job.id}/status',
            'results_url': f'/api/products/{job.id}'
        }), 200

    except Exception as e:
        logging.error(f"Error in API search: {str(e)}")
        return jsonify({'error': 'Something went wrong'}), 500
