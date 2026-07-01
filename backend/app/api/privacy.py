import logging
import json
import re
from fastapi import APIRouter, Depends, HTTPException, status, Response
from fastapi.responses import JSONResponse

from backend.app.core.security import get_current_student
from backend.app.core import database as _db
from backend.app.core.database import export_student_data

logger = logging.getLogger(__name__)
router = APIRouter()

@router.delete("/me/data", status_code=status.HTTP_200_OK)
async def request_data_deletion(student: dict = Depends(get_current_student)):
    """
    Hard delete all personal data associated with the current student.
    Cascades to all tables (reading_progress, student_mastery, exam_attempts, student_chat_history).
    """
    student_id = student["id"]
    username = student["username"]
    
    try:
        async with _db.db_pool.acquire() as conn:
            async with conn.transaction():
                # Perform the deletion
                await conn.execute("DELETE FROM students WHERE id = $1", student_id)
                
        logger.info(f"Privacy Compliance: Hard-deleted all data for student_id={student_id}, username={username}")
        return {
            "status": "success",
            "message": "All user account data has been successfully permanently deleted."
        }
    except Exception as e:
        logger.exception(f"Error performing data deletion for student {username}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error deleting user data from the database."
        )

@router.get("/me/export")
async def export_personal_data(student: dict = Depends(get_current_student)):
    """
    Export all personal, academic, and progress data for the authenticated student in machine-readable JSON format.
    """
    student_id = student["id"]
    username = student["username"]
    
    try:
        data = await export_student_data(student_id)
        
        # Serialize with indent for readability
        json_content = json.dumps(data, indent=2)
        safe_name = re.sub(
            r'[^a-zA-Z0-9_-]',
            '_',
            username
        )[:50]
        
        return Response(
            content=json_content,
            media_type="application/json",
            headers={
                "Content-Disposition": f"attachment; filename=hbse_export_{safe_name}.json"
            }
        )
    except Exception as e:
        logger.exception(f"Error exporting data for student {username}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error exporting user data."
        )
