"""Customer repository."""

import uuid

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.pagination import Page, PaginationParams
from app.common.repositories import BaseRepository
from app.modules.sales.models import Customer
from app.modules.sales.schemas import CustomerCreateRequest, CustomerUpdateRequest


class CustomerRepository(BaseRepository[Customer]):
    """Repository for customer persistence operations."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize the repository with an async database session."""
        super().__init__(session, Customer)

    async def create(self, request: CustomerCreateRequest) -> Customer:
        """Create a customer from request data."""
        customer = Customer(**request.model_dump(), is_active=True)
        return await self.add(customer)

    async def update(
        self,
        customer: Customer,
        request: CustomerUpdateRequest,
    ) -> Customer:
        """Update mutable customer fields from request data."""
        for field_name, value in request.model_dump(exclude_unset=True).items():
            setattr(customer, field_name, value)
        self.session.add(customer)
        await self.session.flush()
        return customer

    async def archive(self, customer: Customer) -> Customer:
        """Mark a customer inactive."""
        customer.is_active = False
        self.session.add(customer)
        await self.session.flush()
        return customer

    async def restore(self, customer: Customer) -> Customer:
        """Restore a customer to active."""
        customer.is_active = True
        self.session.add(customer)
        await self.session.flush()
        return customer

    async def get_by_id(self, customer_id: uuid.UUID) -> Customer | None:
        """Return a non-deleted customer by UUID."""
        statement = select(Customer).where(
            Customer.id == customer_id,
            Customer.is_deleted.is_(False),
        )
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def get_by_customer_code(
        self,
        *,
        business_id: uuid.UUID,
        customer_code: str,
    ) -> Customer | None:
        """Return a customer by business-scoped customer code."""
        statement = select(Customer).where(
            Customer.business_id == business_id,
            Customer.customer_code == customer_code,
            Customer.is_deleted.is_(False),
        )
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def get_by_email(
        self,
        *,
        business_id: uuid.UUID,
        email: str,
    ) -> Customer | None:
        """Return a customer by business-scoped email."""
        statement = select(Customer).where(
            Customer.business_id == business_id,
            Customer.email == email.lower(),
            Customer.is_deleted.is_(False),
        )
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def list_business_customers(
        self,
        business_id: uuid.UUID,
        pagination: PaginationParams | None = None,
    ) -> Page[Customer]:
        """Return paginated customers for a business."""
        params = pagination or PaginationParams()
        statement = (
            select(Customer)
            .where(
                Customer.business_id == business_id,
                Customer.is_deleted.is_(False),
            )
            .order_by(Customer.created_at.desc())
        )
        total = await self._count_statement(statement)
        result = await self.session.execute(
            statement.offset(params.offset).limit(params.limit)
        )
        return Page.create(
            items=list(result.scalars().all()),
            total=total,
            params=params,
        )

    async def exists_by_code(
        self,
        *,
        business_id: uuid.UUID,
        customer_code: str,
    ) -> bool:
        """Return whether a customer code exists for a business."""
        return (
            await self.get_by_customer_code(
                business_id=business_id,
                customer_code=customer_code,
            )
            is not None
        )

    async def exists_by_email(
        self,
        *,
        business_id: uuid.UUID,
        email: str,
    ) -> bool:
        """Return whether a customer email exists for a business."""
        return await self.get_by_email(business_id=business_id, email=email) is not None

    async def _count_statement(self, statement: Select[tuple[Customer]]) -> int:
        """Count rows from a selectable statement."""
        count_statement = select(func.count()).select_from(statement.subquery())
        result = await self.session.execute(count_statement)
        return int(result.scalar_one())
