from sqlalchemy import create_engine, Column, Integer, String, Float, Date, ForeignKey, BigInteger
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
from sqlalchemy.ext.declarative import declared_attr
from datetime import datetime
import os

Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    
    id = Column(BigInteger, primary_key=True)  # Telegram user_id
    username = Column(String(64), nullable=True)
    first_name = Column(String(64), nullable=False)
    last_name = Column(String(64), nullable=True)
    language_code = Column(String(8), nullable=True)
    registration_date = Column(Date, default=datetime.now)
    last_activity = Column(Date, default=datetime.now, onupdate=datetime.now)
    currency = Column(String(3), default='UAH')  # Валюта за замовчуванням
    
    # Відносини
    transactions = relationship("Transaction", back_populates="user")
    budgets = relationship("Budget", back_populates="user")
    goals = relationship("Goal", back_populates="user")
    
    def __repr__(self):
        return f"<User(id={self.id}, username='{self.username}')>"

class Transaction(Base):
    __tablename__ = "transactions"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(BigInteger, ForeignKey('users.id'), nullable=False)
    amount = Column(Float, nullable=False)
    category = Column(String(64), nullable=False)
    description = Column(String(256), nullable=True)
    date = Column(Date, default=datetime.now)
    created_at = Column(Date, default=datetime.now)
    
    # Відносини
    user = relationship("User", back_populates="transactions")
    
    def __repr__(self):
        return f"<Transaction(amount={self.amount}, category='{self.category}')>"

class Budget(Base):
    __tablename__ = 'budgets'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(BigInteger, ForeignKey('users.id'), nullable=False)
    category = Column(String(64), nullable=False)
    limit = Column(Float, nullable=False)
    period = Column(String(16), default='monthly')  # monthly, weekly, yearly
    created_at = Column(Date, default=datetime.now)
    updated_at = Column(Date, default=datetime.now, onupdate=datetime.now)
    
    # Відносини
    user = relationship("User", back_populates="budgets")
    
    def __repr__(self):
        return f"<Budget(category='{self.category}', limit={self.limit})>"

class Goal(Base):
    __tablename__ = "goals"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(BigInteger, ForeignKey('users.id'), nullable=False)
    name = Column(String(128), nullable=False)
    target_amount = Column(Float, nullable=False)
    current_amount = Column(Float, default=0.0)
    deadline = Column(Date, nullable=True)
    created_at = Column(Date, default=datetime.now)
    
    # Відносини
    user = relationship("User", back_populates="goals")
    
    def __repr__(self):
        return f"<Goal(name='{self.name}', target={self.target_amount})>"

# Підключення до БД
DB_URL = os.getenv("DB_URL", "sqlite:///finance_bot.db")  # За замовчуванням SQLite
engine = create_engine(DB_URL)
Session = sessionmaker(bind=engine)

def init_db():
    """Ініціалізація бази даних"""
    Base.metadata.create_all(engine)
    print("Database tables created successfully.")

if __name__ == "__main__":
    init_db()