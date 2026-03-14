from fastapi import APIRouter, HTTPException
from services import (
    get_cohort_summary,
    get_age_distribution,
    get_enrollment_timeline,
    get_site_group_matrix,
)

router = APIRouter(prefix="/api/cohort", tags=["cohort"])


@router.get("/summary")
def cohort_summary():
    """Full cohort aggregate summary — used on the Overview dashboard page."""
    try:
        return get_cohort_summary()
    except FileNotFoundError as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.get("/age-distribution")
def age_distribution():
    """Age histogram buckets in 5-year intervals."""
    return get_age_distribution()


@router.get("/enrollment")
def enrollment_timeline():
    """Monthly enrollment counts + cumulative total."""
    return get_enrollment_timeline()


@router.get("/site-group-matrix")
def site_group_matrix():
    """Participant counts broken down by site × study group."""
    return get_site_group_matrix()
