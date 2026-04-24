from fastapi import APIRouter, Depends

from app.db import get_db
from app.services.aggregation_service import (
    apartment_details,
    building_details,
    city_details,
    navigation_overview,
)


router = APIRouter(prefix="/api/navigation", tags=["navigation"])


@router.get("/overview")
def overview(connection=Depends(get_db)):
    return navigation_overview(connection)


@router.get("/cities/{city_id}")
def city(city_id: str, connection=Depends(get_db)):
    return city_details(connection, city_id)


@router.get("/buildings/{building_id}")
def building(building_id: str, connection=Depends(get_db)):
    return building_details(connection, building_id)


@router.get("/apartments/{apartment_id}")
def apartment(apartment_id: str, connection=Depends(get_db)):
    return apartment_details(connection, apartment_id)
