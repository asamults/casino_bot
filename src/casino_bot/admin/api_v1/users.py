"""Domain users: catalog, detail, create, token adjust, subscription reads (Admin API v1)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import TypeAdapter
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from casino_bot.admin.api_v1.schemas import (
    ActivateTestPlanBody,
    LinkSubscriptionBody,
    SubscriptionListResponse,
    SubscriptionSummaryOut,
    TokenAccountOut,
    TokenAdjustBody,
    UserCreateBody,
    UserDetailOut,
    UsersListResponse,
    UserListItemOut,
)
from casino_bot.admin.deps import admin_guard, superadmin_guard
from casino_bot.core.database import get_db
from casino_bot.db.models import User
from casino_bot.services import economy_service
from casino_bot.services.subscription_admin_service import (
    activate_internal_test_plan,
    deactivate_internal_test_plan,
    get_subscriptions_for_user,
    link_test_subscription,
)
from casino_bot.services.user_catalog_service import get_user_detail, list_users
from casino_bot.services.entitlement_policy import enforce_if_required

router = APIRouter(tags=["admin"])

_MAX_LIMIT = 100
_DEFAULT_LIMIT = 20


@router.get("", response_model=UsersListResponse)
def api_list_users(
    db: Session = Depends(get_db),
    _: dict = Depends(admin_guard()),
    skip: int = Query(0, ge=0),
    limit: int = Query(_DEFAULT_LIMIT, ge=1, le=_MAX_LIMIT),
    is_active: bool | None = Query(None),
    telegram_user_id: int | None = Query(None),
    whatsapp_search: str | None = Query(
        None, description="Substring match on whatsapp_phone_e164"
    ),
):
    """Paginated user catalog with optional filters."""
    rows, total = list_users(
        db,
        skip=skip,
        limit=limit,
        is_active=is_active,
        telegram_user_id=telegram_user_id,
        whatsapp_contains=whatsapp_search,
    )
    items = TypeAdapter(list[UserListItemOut]).validate_python(rows)
    return UsersListResponse(items=items, total=total)


@router.get("/{user_id}", response_model=UserDetailOut)
def api_get_user(
    user_id: int,
    db: Session = Depends(get_db),
    _: dict = Depends(admin_guard()),
):
    user = get_user_detail(db, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    subs = [
        SubscriptionSummaryOut.model_validate(s) for s in (user.subscriptions or [])
    ]
    ta = user.token_account
    detail = UserDetailOut(
        id=user.id,
        created_at=user.created_at,
        is_active=user.is_active,
        internal_note=user.internal_note,
        telegram_user_id=user.telegram_user_id,
        whatsapp_phone_e164=user.whatsapp_phone_e164,
        billing_customer_id=user.billing_customer_id,
        token_account=TokenAccountOut.model_validate(ta) if ta is not None else None,
        subscriptions=subs,
    )
    return detail


@router.post("", status_code=status.HTTP_201_CREATED)
def api_create_user(
    payload: UserCreateBody,
    db: Session = Depends(get_db),
    admin: dict = Depends(admin_guard()),
):
    actor = str(admin.get("sub") or "unknown")
    try:
        user = economy_service.create_user(
            db,
            actor=actor,
            internal_note=payload.internal_note,
            telegram_user_id=payload.telegram_user_id,
            whatsapp_phone_e164=payload.whatsapp_phone_e164,
            billing_customer_id=payload.billing_customer_id,
        )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Unique constraint violated (telegram_user_id, whatsapp_phone_e164, or billing_customer_id)",
        ) from exc
    return {"id": user.id, "is_active": user.is_active}


@router.post("/{user_id}/tokens/adjust")
def api_adjust_tokens(
    user_id: int,
    payload: TokenAdjustBody,
    db: Session = Depends(get_db),
    admin: dict = Depends(admin_guard()),
):
    """Adjust token balance; compliance violations return **409** with ``code: COMPLIANCE_VIOLATION`` (global handler)."""
    actor = str(admin.get("sub") or "unknown")
    if str(admin.get("role") or "") != "superadmin":
        enforce_if_required("user.tokens.adjust", db=db, user_id=user_id)
    try:
        account = economy_service.adjust_user_tokens(
            db,
            user_id=user_id,
            delta=payload.delta,
            reason=payload.reason,
            actor=actor,
        )
        db.commit()
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"user_id": user_id, "balance": account.balance}


@router.get("/{user_id}/subscription", response_model=SubscriptionListResponse)
def api_list_user_subscriptions(
    user_id: int,
    db: Session = Depends(get_db),
    _: dict = Depends(admin_guard()),
):
    rows = get_subscriptions_for_user(db, user_id)
    items = TypeAdapter(list[SubscriptionSummaryOut]).validate_python(rows)
    return SubscriptionListResponse(items=items, total=len(items))


@router.post(
    "/{user_id}/subscription/activate-test",
    summary="Activate internal test subscription (superadmin)",
)
def api_activate_test_subscription(
    user_id: int,
    payload: ActivateTestPlanBody,
    db: Session = Depends(get_db),
    admin: dict = Depends(superadmin_guard()),
):
    """Manual subscription row for entitlement testing (no external billing)."""
    if db.query(User).filter(User.id == user_id).first() is None:
        raise HTTPException(status_code=404, detail="User not found")
    actor = str(admin.get("sub") or "unknown")
    sub = activate_internal_test_plan(
        db,
        user_id=user_id,
        plan_code=payload.plan_code,
        actor_email=actor,
        period_days=payload.period_days,
    )
    db.commit()
    return SubscriptionSummaryOut.model_validate(sub)


@router.post(
    "/{user_id}/subscription/deactivate-test",
    summary="Deactivate test subscription (superadmin)",
)
def api_deactivate_test_subscription(
    user_id: int,
    db: Session = Depends(get_db),
    admin: dict = Depends(superadmin_guard()),
):
    if db.query(User).filter(User.id == user_id).first() is None:
        raise HTTPException(status_code=404, detail="User not found")
    actor = str(admin.get("sub") or "unknown")
    affected = deactivate_internal_test_plan(db, user_id=user_id, actor_email=actor)
    db.commit()
    return {"status": "ok", "affected": affected}


@router.post(
    "/{user_id}/subscription/link-test",
    summary="Link provider customer/subscription IDs for webhook tests (superadmin)",
)
def api_link_subscription_test(
    user_id: int,
    payload: LinkSubscriptionBody,
    db: Session = Depends(get_db),
    admin: dict = Depends(superadmin_guard()),
):
    if db.query(User).filter(User.id == user_id).first() is None:
        raise HTTPException(status_code=404, detail="User not found")
    actor = str(admin.get("sub") or "unknown")
    sub = link_test_subscription(
        db,
        user_id=user_id,
        actor_email=actor,
        provider=payload.provider,
        provider_customer_id=payload.provider_customer_id,
        provider_subscription_id=payload.provider_subscription_id,
        plan_code=payload.plan_code,
        status=payload.status,
    )
    db.commit()
    return SubscriptionSummaryOut.model_validate(sub)
