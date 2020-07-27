"""Thsi script generates summary for deposition and erosion from rasters included in a folder"""
#import packages
import ogr
import os
import pathlib
import gdal
import numpy as np
import math
import pandas as pd


#Main Program
#get the current file directory and set relative path to other folders
scriptPath=pathlib.Path(__file__).parent.absolute()
centerLinePath=os.path.abspath(os.path.join(scriptPath,"../Outputs/Shapefiles"))
demFolder=os.path.abspath(os.path.join(scriptPath,"../Outputs/Area-wise Raster"))    

#Open input Raster and get its spatial reference
details = pd.DataFrame(columns=["Section","Total_Area","Total_volume","Average_Depth","Sd_depth","max_erosion","max_deposit","perUnitDeposit"])

for file in os.listdir(demFolder):
    filename,extension=os.path.basename(file).split(".")[0],os.path.basename(file).split(".")[-1]
    if extension in ['tif','tiff','TIF','TIFF']:
        demFile=file
        demRaster=os.path.join(demFolder,demFile)
        inRaster=gdal.Open(demRaster)
        dtmSRS=inRaster.GetProjection()
        
        #Create output raster
        outRaster=os.path.join(demFolder,"volume.tif")
        
        #Read properties of input raster
        inGeotransform=inRaster.GetGeoTransform()
        cellSize=inGeotransform[1]
        
        in_band=inRaster.GetRasterBand(1)
        data=in_band.ReadAsArray()
        mask=abs(data)<5
        masked=data[mask]
        area = masked.size *cellSize*cellSize
        local_volume=masked*cellSize*cellSize
        total_volume=local_volume.sum()
        avgDepth=masked.mean()
        sd_depth=np.std(masked)
        minimum=masked.min()
        maximum=masked.max()
        perUnitDeposit=total_volume/area
        print("Section: {Section}".format(Section=filename))
        print("Total Area: {Area}".format(Area=area))
        print ("total volume:{volume}".format(volume=total_volume))
        print("Average Depth:{avgDepth}".format(avgDepth=avgDepth))
        print("Standard deviatio of depth:{sd_depth}".format(sd_depth=np.std(masked)))
        print("Maximum erosion depth:{minimum}".format(minimum=masked.min()))
        print("Maximum deposition depth:{maximum}".format(maximum=masked.max()))
        print ("########")
        details=details.append({"Section":filename,"Total_Area":area,"Total_volume":total_volume,"Average_Depth":avgDepth,"Sd_depth":sd_depth,"max_erosion":minimum,"max_deposit":maximum,"perUnitDeposit":perUnitDeposit}, ignore_index=True)
details.to_csv(os.path.join(demFolder,"volume.csv"))