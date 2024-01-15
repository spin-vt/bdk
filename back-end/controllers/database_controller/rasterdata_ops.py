from database.sessions import Session
from database.models import rasterdata
from sqlalchemy.orm.exc import NoResultFound, MultipleResultsFound
from sqlalchemy.exc import SQLAlchemyError

def create_rasterdata(tower_id, image_data, transparent_image_data, loss_color_mapping, nbound, sbound, ebound, wbound, session=None):
    owns_session = False
    if session is None:
        session = Session()
        owns_session = True
    try:
        # Create RasterData instance and add to the Tower instance
        new_raster_data = rasterdata(tower_id=tower_id, image_data=image_data, transparent_image_data=transparent_image_data, loss_color_mapping=loss_color_mapping, north_bound=nbound, south_bound=sbound, east_bound=ebound, west_bound=wbound)
        
        session.add(new_raster_data)

        if owns_session:
            session.commit()
        return new_raster_data
    except SQLAlchemyError as e:
        if owns_session:
            session.rollback()
        return f"An error occurred while adding raster data to the tower: {e}"
    finally:
        if owns_session:
            session.close()