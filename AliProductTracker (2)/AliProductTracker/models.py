from app import db
from datetime import datetime
import json

class ScrapingJob(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    search_term = db.Column(db.String(200), nullable=False)
    status = db.Column(db.String(50), default='pending')  # pending, running, completed, failed
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime)
    total_pages = db.Column(db.Integer, default=1)
    current_page = db.Column(db.Integer, default=0)
    error_message = db.Column(db.Text)
    
    # Relationship to products
    products = db.relationship('Product', backref='job', lazy=True, cascade='all, delete-orphan')
    
    def to_dict(self):
        return {
            'id': self.id,
            'search_term': self.search_term,
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'total_pages': self.total_pages,
            'current_page': self.current_page,
            'error_message': self.error_message,
            'product_count': len(self.products)
        }

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    job_id = db.Column(db.Integer, db.ForeignKey('scraping_job.id'), nullable=False)
    title = db.Column(db.Text, nullable=False)
    price = db.Column(db.String(100))
    original_price = db.Column(db.String(100))
    rating = db.Column(db.Float)
    review_count = db.Column(db.Integer)
    seller_name = db.Column(db.String(200))
    product_url = db.Column(db.Text)
    image_url = db.Column(db.Text)
    shipping_info = db.Column(db.String(200))
    discount_percentage = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'price': self.price,
            'original_price': self.original_price,
            'rating': self.rating,
            'review_count': self.review_count,
            'seller_name': self.seller_name,
            'product_url': self.product_url,
            'image_url': self.image_url,
            'shipping_info': self.shipping_info,
            'discount_percentage': self.discount_percentage
        }
