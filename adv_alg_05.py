# Реализовать сохранение полученных данных в Базу данных
# используя ORM SQLAlchemy. А также разработать
# полноценную структуру БД на SQLAlchemy

from abc import ABC, abstractmethod
from sqlalchemy.orm import declarative_base, declared_attr, relationship
from sqlalchemy import create_engine, Column, Integer, String, Float, ForeignKey, DateTime, func
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import os
from contextlib import contextmanager
import psycopg2
from typing import List, Optional
from pydantic import BaseModel as PydanticBaseModel


# 1. Создание базы данных
def create_database():
    try:
        conn = psycopg2.connect(
            dbname="postgres",
            user="postgres",
            password="yourpassword",
            host="localhost"
        )
        conn.autocommit = True
        cursor = conn.cursor()

        cursor.execute("SELECT 1 FROM pg_database WHERE datname='synergy'")
        exists = cursor.fetchone()

        if not exists:
            cursor.execute("CREATE DATABASE synergy")
            print("База данных 'synergy' успешно создана")
        else:
            print("База данных 'synergy' уже существует")

        cursor.close()
        conn.close()
    except Exception as e:
        print(f"Ошибка при создании базы данных: {e}")


create_database()

Base = declarative_base()


# Класс для управления подключением к БД
class DatabaseConnection:
    def __init__(self, db_url: str = None):
        self.db_url = db_url or os.getenv('DATABASE_URL') or "postgresql://postgres:yourpassword@localhost:5432/synergy"
        self.engine = create_engine(self.db_url)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)

    @contextmanager
    def get_session(self):
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def create_tables(self):
        Base.metadata.create_all(bind=self.engine)


# Базовый класс для таблиц
class BaseTable(Base):
    __abstract__ = True

    @declared_attr
    def __tablename__(cls):
        return cls.__name__.lower()

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)

    @abstractmethod
    def to_dict(self):
        pass


# 1.A. Товары зависят от поставщика (реализовано через ForeignKey)
class Supplier(BaseTable):
    name = Column(String(100), nullable=False, unique=True)
    contact_person = Column(String(100))
    phone = Column(String(20))
    email = Column(String(100))
    address = Column(String(200))

    products = relationship("Product", back_populates="supplier", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "contact_person": self.contact_person,
            "phone": self.phone,
            "email": self.email,
            "address": self.address,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }


class Product(BaseTable):
    name = Column(String(100), nullable=False)
    description = Column(String(500))
    price = Column(Float, nullable=False)
    quantity = Column(Integer, default=0)
    supplier_id = Column(Integer, ForeignKey('supplier.id', ondelete="CASCADE"), nullable=False)

    supplier = relationship("Supplier", back_populates="products")
    order_items = relationship("OrderItem", back_populates="product")

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "price": self.price,
            "quantity": self.quantity,
            "supplier_id": self.supplier_id,
            "supplier_name": self.supplier.name if self.supplier else None,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }


# 1.B. Заказы зависят от товаров (через таблицу OrderItem)
class Order(BaseTable):
    customer_name = Column(String(100), nullable=False)
    customer_phone = Column(String(20))
    customer_email = Column(String(100))
    status = Column(String(50), default="created")
    total_amount = Column(Float, default=0.0)

    items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")

    def calculate_total(self):
        self.total_amount = sum(item.price * item.quantity for item in self.items)
        return self.total_amount

    def to_dict(self):
        return {
            "id": self.id,
            "customer_name": self.customer_name,
            "customer_phone": self.customer_phone,
            "customer_email": self.customer_email,
            "status": self.status,
            "total_amount": self.total_amount,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "items": [item.to_dict() for item in self.items]
        }


class OrderItem(BaseTable):
    order_id = Column(Integer, ForeignKey('order.id', ondelete="CASCADE"), nullable=False)
    product_id = Column(Integer, ForeignKey('product.id'), nullable=False)
    quantity = Column(Integer, nullable=False, default=1)
    price = Column(Float, nullable=False)  # Цена на момент заказа

    order = relationship("Order", back_populates="items")
    product = relationship("Product", back_populates="order_items")

    def to_dict(self):
        return {
            "id": self.id,
            "order_id": self.order_id,
            "product_id": self.product_id,
            "product_name": self.product.name if self.product else None,
            "quantity": self.quantity,
            "price": self.price,
            "total": self.price * self.quantity,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }


# 3. Реализация ODT классов с помощью Pydantic
class SupplierODT(PydanticBaseModel):
    id: Optional[int] = None
    name: str
    contact_person: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ProductODT(PydanticBaseModel):
    id: Optional[int] = None
    name: str
    description: Optional[str] = None
    price: float
    quantity: int = 0
    supplier_id: int
    supplier_name: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class OrderItemODT(PydanticBaseModel):
    id: Optional[int] = None
    product_id: int
    product_name: Optional[str] = None
    quantity: int = 1
    price: float
    total: Optional[float] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class OrderODT(PydanticBaseModel):
    id: Optional[int] = None
    customer_name: str
    customer_phone: Optional[str] = None
    customer_email: Optional[str] = None
    status: str = "created"
    total_amount: float = 0.0
    items: List[OrderItemODT] = []
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

if __name__ == "__main__":
    db = DatabaseConnection()
    db.create_tables()

    # Создаем тестовые данные
    with db.get_session() as session:
        # Проверяем, существует ли уже поставщик
        supplier = session.query(Supplier).filter_by(name="TechSupplier Inc.").first()

        if not supplier:
            # Создаем поставщика только если он не существует
            supplier = Supplier(
                name="TechSupplier Inc.",
                contact_person="Иван Иванов",
                phone="+79991234567",
                email="tech@example.com",
                address="Москва, ул. Техническая, 42"
            )
            session.add(supplier)
            session.commit()
            print("Создан новый поставщик")
        else:
            print("Поставщик уже существует, используем существующего")

        # Проверяем существование товаров
        product1 = session.query(Product).filter_by(name="Ноутбук игровой").first()
        if not product1:
            product1 = Product(
                name="Ноутбук игровой",
                description="Мощный игровой ноутбук",
                price=85000.0,
                quantity=15,
                supplier_id=supplier.id
            )
            session.add(product1)
            print("Создан новый товар 1")

        product2 = session.query(Product).filter_by(name="Смартфон").first()
        if not product2:
            product2 = Product(
                name="Смартфон",
                description="Флагманский смартфон",
                price=65000.0,
                quantity=30,
                supplier_id=supplier.id
            )
            session.add(product2)
            print("Создан новый товар 2")

        session.commit()

        # Создаем новый заказ (можно создавать каждый раз, так как нет unique constraint)
        order = Order(
            customer_name="Петр Петров",
            customer_phone="+79998765432",
            customer_email="petrov@example.com"
        )

        # Добавляем товары в заказ
        order_item1 = OrderItem(
            order=order,
            product=product1,
            quantity=1,
            price=product1.price
        )

        order_item2 = OrderItem(
            order=order,
            product=product2,
            quantity=2,
            price=product2.price
        )

        order.items.extend([order_item1, order_item2])
        order.calculate_total()

        session.add(order)
        session.commit()
        print("Создан новый заказ")

    # 2. Получение данных из таблицы заказов и вывод на экран
    with db.get_session() as session:
        print("\nВсе заказы из базы данных:")
        orders = session.query(Order).all()

        if not orders:
            print("Нет заказов в базе данных")
        else:
            for order in orders:
                print(f"\nЗаказ #{order.id}:")
                print(f"Клиент: {order.customer_name}")
                print(f"Телефон: {order.customer_phone}")
                print(f"Email: {order.customer_email}")
                print(f"Статус: {order.status}")
                print(f"Сумма: {order.total_amount} руб.")
                print("Товары:")
                for item in order.items:
                    print(f"  - {item.product.name} ({item.quantity} x {item.price} руб.)")

    # 4. Преобразование в ODT и вывод данных
    with db.get_session() as session:
        # Получаем первый заказ
        order = session.query(Order).first()

        if order:
            # Преобразуем в ODT
            order_odt = OrderODT.model_validate(order)

            print("\nДанные заказа в формате ODT:")
            print(order_odt.model_dump_json(indent=2))
        else:
            print("Нет заказов для преобразования в ODT")