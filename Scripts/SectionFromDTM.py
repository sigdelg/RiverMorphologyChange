"""This script generates multi-temporal drawings for cross-sections overlaid to each other on yearly basis. Inputs required are reference centerline,and multi-temporal DEMs"""
import math
import pandas as pd
import geopandas as gpd
import numpy as np
import fiona
from shapely.geometry import Point, MultiLineString, LineString
import matplotlib.pyplot as plt
import ogr
import gdal
import os
import pathlib
import seaborn as sns
sns.set()

def CoordToIndex(geoTransform, x,y):
    """Return the offset of the provided co-ordinate from origin of raster"""
    invGeotransform = gdal.InvGeoTransform(geoTransform)
    x1,y1=gdal.ApplyGeoTransform(invGeotransform,x,y)
    columnPosition,RowPosition=int(x1),int(y1)
    return(columnPosition,RowPosition)

#Calculate distance and bearing between two points
def distance(p0, p1):
    deltaE, deltaN=p1[0]-p0[0],p1[1]-p0[1]
    distance=math.sqrt(deltaE**2+deltaN**2)
    return distance

#Calculate bearing of a line joining two points in order(E,N)
def bearing(p0,p1):
    deltaE, deltaN=p1[0]-p0[0],p1[1]-p0[1]
    if deltaE==0 and deltaN>0:
        bearing=0
    elif deltaE==0 and deltaN<0:
        bearing=math.pi
    elif deltaE<0 and deltaN==0:
        bearing=1.5*math.pi
    elif deltaE>0 and deltaN==0:
        bearing=math.pi/2
    elif deltaN<0:
        bearing=math.pi+math.atan(deltaE/deltaN)
    elif deltaE<0 and deltaN>0:
        bearing=2*math.pi+math.atan(deltaE/deltaN)
    else:
        bearing=math.atan(deltaE/deltaN)
    return bearing

def createSectionLines(centerline,interval,width):
    """
    Creates cross-section at user specified interval and of user-entered width, perpendicular to alignment.

    Parameters
    ----------
    centerline : GEODATAFRAME OBJECT
        The centreline based on which cross-section lines are to be generated
    interval : FLOAT 
        The interval along the centerline between two succesive cross-sections
    width : RLOAT
        The  width on each side of centerline to generate cross-section for

    Returns
    -------
    gdf : GEODATAFRAME OBJECT
        Geodataframe object containing cross-section lines

    """
    #Extract vertices of centerline
    vertices=[centerline.geometry[0].coords[i] for i in range(len(centerline.geometry[0].coords))]
    chainages=[]
    chainage=0
    for i in range(len(vertices)):
        if i==0:
           chainages.append(0)
        else:
            segmentLength=distance(vertices[i-1],vertices[i])
            chainage+=segmentLength
            chainages.append(chainage)
            
     #Create dataframe to store sections
    sections=pd.DataFrame(columns=['sectionId','geometry','chainage'])
    ch=0;
    while ch<=chainages[-1]:
        for i in range(len(chainages)):
            #Determine center point of cross-sections
            if chainages[i]<=ch and chainages[i+1]>ch:
                #Interpolate values
                ch_x=vertices[i][0]+(vertices[i+1][0]-vertices[i][0])*(ch-chainages[i])/(chainages[i+1]-chainages[i])
                ch_y=vertices[i][1]+(vertices[i+1][1]-vertices[i][1])*(ch-chainages[i])/(chainages[i+1]-chainages[i])
                sectionpoint=(ch_x,ch_y)
                #Compute Bearing to the left
                LocalBearing=bearing(sectionpoint,vertices[i+1])
                sectionBearing=LocalBearing+math.pi/2
                leftx=ch_x-width*math.sin(sectionBearing)
                lefty=ch_y -width*math.cos(sectionBearing)
                rightx=ch_x+width*math.sin(sectionBearing)
                righty=ch_y+width*math.cos(sectionBearing)
                sectionCoordinates=LineString(coordinates=[(leftx, lefty),(ch_x,ch_y),(rightx, righty)])
                sectionId="Chainage "+str(ch)
                #print (sectionCoordinates)
                rowData=pd.DataFrame({"sectionId":[sectionId],"geometry":[sectionCoordinates],"chainage":ch})
                sections=sections.append(rowData)
        ch+=interval
    sections.index=[i for i in range(len(sections))]
    gdf =gpd.GeoDataFrame(sections,geometry='geometry')
    return gdf


def populateCrossSection(sections,n_points,rasterFolder):
    """
    Creates the points along cross-section from the raster, based on specified no. of points

    Parameters
    ----------
    sections : PANDAS DATAFRAME
        The datafrom containing each of the section lines as line(dataframe)
    n_points : INTEGER
        No. of points to be generated along the selected line
    rasterFolder : OS PATH
        Path to folder containing all rasters, from which cross-sections are to be generated.

    Returns
    -------
    None.

    """
    demSections=gpd.GeoDataFrame()
    for file in os.listdir(rasterFolder):
        filename=file.split(".")[0]
        extension=file.split(".")[-1]
        if extension in ["tif","TIF","tiff","TIFF"]:
            rasterPath=os.path.join(rasterFolder,file)
    
            #Read Raster
            inRaster=gdal.Open(rasterPath)
            dtmSRS=inRaster.GetProjection()
            #Read properties of input raster
            inGeotransform=inRaster.GetGeoTransform()
            
            in_band=inRaster.GetRasterBand(1)
            #Create blank geopandas
            sectionData=gpd.GeoDataFrame()
            #Populate n points along the section
            for ind, row in sections.iterrows():
                
                XS_ID = row['sectionId']
            
                start_coords =  list([row.geometry][0].coords)[0]
                end_coords = list([row.geometry][0].coords)[2]
                
                x = [start_coords[0]]
                y = [start_coords[1]]
                
                n_points = 250
                
                for i in np.arange(1, n_points+1):
                    x_dist = end_coords[0] - start_coords[0]
                    y_dist = end_coords[1] - start_coords[1]
                    point  = [(start_coords[0] + (x_dist/(n_points+1))*i), (start_coords[1] + (y_dist/(n_points+1))*i)]
                    x.append(point[0])
                    y.append(point[1])
                    
                x.append(end_coords[0])
                y.append(end_coords[1])
                
                
                df = pd.DataFrame({'x_coord': x, 'y_coord': y})  
                gdf = gpd.GeoDataFrame(df, geometry = gpd.points_from_xy(df.x_coord,df.y_coord))
                gdf['h_distance'] = 0
                gdf['Year']=filename
                gdf['Elevation']=0
                gdf['sectionId']=XS_ID
                for index, row in gdf.iterrows():
                    gdf['h_distance'].loc[index] = gdf.geometry[0].distance(gdf.geometry[index])-gdf.geometry[0].distance(gdf.geometry[len(gdf.geometry)-1])/2
                    gdf['Elevation'].loc[index] = in_band.ReadAsArray((CoordToIndex(inGeotransform, gdf.geometry.x[index],gdf.geometry.y[index]))[0],(CoordToIndex(inGeotransform, gdf.geometry[index].x,gdf.geometry[index].y))[1],1,1)
                #sectionData=sectionData.append(gdf)
                demSections=demSections.append(gdf)
    return(demSections)
 
    
#Main Program
#get the current file directory and set relative path to other folders
scriptPath=pathlib.Path(__file__).parent.absolute()
centerLinePath=os.path.abspath(os.path.join(scriptPath,"../Outputs/Shapefiles"))
demFolder=os.path.abspath(os.path.join(scriptPath,"../Outputs/DTM"))    

#Read shapefile
centerline=gpd.read_file(os.path.join(centerLinePath,"River_Centerline.shp"))
#Section lines at 25m interval,15m on each side
sections=createSectionLines(centerline,25,15)       
#Batch process  for all tiff images
sectionData=populateCrossSection(sections,50, demFolder)
#Sectionwise plot
uniqueSectionId=sectionData['sectionId'].unique()
#Create dynamic subplot
categorical_vars = uniqueSectionId
num_plots = len(categorical_vars)+1
total_cols=2
total_rows = num_plots//total_cols + 1
fig,axs = plt.subplots(total_rows, ncols=total_cols,
                         figsize=(7*total_cols, 7*total_rows), constrained_layout=False)

for i, var in enumerate(categorical_vars):
     row = i//total_cols
     pos = i % total_cols
     sns.lineplot(x="h_distance", y="Elevation",hue="Year", estimator=None,ci=None,lw=1,data=sectionData[sectionData['sectionId']==var],ax=axs[row][pos]).set_title('Change in section at {section}'.format(section=var))
     plt.axis('equal')
plt.tight_layout()
