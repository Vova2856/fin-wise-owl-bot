import logging
from datetime import datetime
from database import Session, User, Transaction, Budget, Goal
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import func

logger = logging.getLogger(__name__)

async def get_or_create_user(user_id: int, username: str, first_name: str, last_name: str = None, language_code: str = None):
    session = Session()
    try:
        user = session.query(User).filter_by(id=user_id).first()
        if not user:
            user = User(
                id=user_id,
                username=username,
                first_name=first_name,
                last_name=last_name,
                language_code=language_code
            )
            session.add(user)
            session.commit()
            logger.info(f"New user added: {user_id}")
        else:
            user.last_activity = datetime.now()
            session.commit()
        return user
    except SQLAlchemyError as e:
        session.rollback()
        logger.error(f"Error getting/creating user {user_id}: {e}")
        return None
    finally:
        session.close()

async def add_transaction(user_id: int, amount: float, transaction_type: str, category: str, description: str = None):
    session = Session()
    try:
        transaction = Transaction(
            user_id=user_id,
            amount=amount,
            type=transaction_type,
            category=category,
            description=description,
            date=datetime.now()
        )
        session.add(transaction)
        session.commit()
        logger.info(f"Transaction added: {user_id}, {amount}, {category}")
        return True
    except SQLAlchemyError as e:
        session.rollback()
        logger.error(f"Error adding transaction: {e}")
        return False
    finally:
        session.close()

async def get_transactions(user_id: int, limit: int = 10):
    session = Session()
    try:
        transactions = session.query(Transaction).filter_by(user_id=user_id)\
                              .order_by(Transaction.date.desc())\
                              .limit(limit).all()
        return transactions
    except SQLAlchemyError as e:
        logger.error(f"Error getting transactions: {e}")
        return []
    finally:
        session.close()

async def get_balance(user_id: int):
    session = Session()
    try:
        income = session.query(func.sum(Transaction.amount))\
                       .filter(Transaction.user_id == user_id, Transaction.type == 'income')\
                       .scalar() or 0.0
        
        expense = session.query(func.sum(Transaction.amount))\
                        .filter(Transaction.user_id == user_id, Transaction.type == 'expense')\
                        .scalar() or 0.0
        
        return income - expense
    except SQLAlchemyError as e:
        logger.error(f"Error calculating balance: {e}")
        return 0.0
    finally:
        session.close()