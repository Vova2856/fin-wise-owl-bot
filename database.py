from sqlalchemy import create_engine, Column, Integer, String, Float, Date, ForeignKey, BigInteger
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
from datetime import datetime
import os
import logging

logger = logging.getLogger(__name__)

Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    
    id = Column(BigInteger, primary_key=True)
    username = Column(String(64), nullable=True)
    first_name = Column(String(64), nullable=False)
    last_name = Column(String(64), nullable=True)
    language_code = Column(String(8), nullable=True)
    registration_date = Column(Date, default=datetime.now)
    last_activity = Column(Date, default=datetime.now, onupdate=datetime.now)
    currency = Column(String(3), default='UAH')
    
    transactions = relationship("Transaction", back_populates="user", cascade="all, delete-orphan")
    budgets = relationship("Budget", back_populates="user", cascade="all, delete-orphan")
    goals = relationship("Goal", back_populates="user", cascade="all, delete-orphan")

class Transaction(Base):
    __tablename__ = "transactions"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(BigInteger, ForeignKey('users.id'), nullable=False)
    amount = Column(Float, nullable=False)
    type = Column(String(16), nullable=False)  # 'income' or 'expense'
    category = Column(String(64), nullable=False)
    description = Column(String(256), nullable=True)
    date = Column(Date, default=datetime.now)
    
    user = relationship("User", back_populates="transactions")

class Budget(Base):
    __tablename__ = 'budgets'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(BigInteger, ForeignKey('users.id'), nullable=False)
    category = Column(String(64), nullable=False)
    limit = Column(Float, nullable=False)
    period = Column(String(16), default='monthly')
    created_at = Column(Date, default=datetime.now)
    updated_at = Column(Date, default=datetime.now, onupdate=datetime.now)
    
    user = relationship("User", back_populates="budgets")

class Goal(Base):
    __tablename__ = "goals"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(BigInteger, ForeignKey('users.id'), nullable=False)
    name = Column(String(128), nullable=False)
    target_amount = Column(Float, nullable=False)
    current_amount = Column(Float, default=0.0)
    months = Column(Integer, nullable=False)
    created_at = Column(Date, default=datetime.now)
    description = Column(String(256), nullable=True)
    
    user = relationship("User", back_populates="goals")

DB_URL = os.getenv("DB_URL", "sqlite:///finance_bot.db") 
engine = create_engine(DB_URL)
Session = sessionmaker(bind=engine)

def init_db():
    try:
        Base.metadata.create_all(engine)
        logger.info("Database tables created successfully")
    except Exception as e:
        logger.error(f"Error creating database tables: {e}", exc_info=True)