import math
import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt
from shapely.geometry import Point, MultiLineString, LineString
import os
import pathlib
import seaborn as sns
sns.set()



def renameFiles(folder,section_df):
    """
    Renames the csv files generated from point cloud to match corresponding section name in cross-section dataframe""

    Parameters
    ----------
    folder : String
        Location of the main folder containing sections extracted from cloud compare
    section_df : Geo-dataframe object
        Should contains cross-sections with "sectionId" column

    Returns
    -------
    None.

    """
    i=0
    for root, dirs, files in os.walk(folder,topdown=True):
        for name in files:
            if name.startswith("Section cloud"):
                fullpath=os.path.join(root,name)
                csvname,extension=name.split(".")
                label,chainage=csvname.split("#")
                chainageSequence=int(chainage)-1
                newName=section_df.iloc[chainageSequence]['sectionId']+'.csv'
                os.rename(fullpath, os.path.join(root,newName))
                print("{oldname} renamed as {newname}".format(oldname=name, newname=newName))
                i+=1
    print ("{numFiles} files renamed".format(numFiles=i))
    
def distance(p0, p1):
    deltaE, deltaN=p1[0]-p0[0],p1[1]-p0[1]
    distance=math.sqrt(deltaE**2+deltaN**2)
    return distance

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

def Project(start,end,point):
    point_length=math.sqrt((point[0]-start[0])**2+(point[1]-start[1])**2)
    reference_bearing=bearing(start,end)
    point_bearing = bearing(start,point)
    deltaBearing = point_bearing -reference_bearing
    #Project on referenceline
    chainage= point_length*math.cos(deltaBearing)
    offset=point_length*math.sin(deltaBearing)
    return chainage,offset

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
    print ("Section lines successfully generated.")
    return gdf

def createData(sections,folder):
    """
    Create ready-to-plot cross-section data taking reference cross-section and the folders containing chainage-wise point cloud as csv.

    Parameters
    ----------
    sections : GEODATAFRAME OBJECT
        Geodatadataframe storing no. of cross-sections, each as a multlilinestring
    folder : STRING
        Folder Containing Cross-sections point cloud

    Returns
    dfObj : GEODATAFRAME OBJECT
        Projected cross-sections with chainage, distance and RL

    """
    dfObj=pd.DataFrame()
    for i in range(len(sections)):
        sectionName=sections.iloc[i]
        filename=sectionName.sectionId
        centre=sectionName.geometry.coords[1]
        end=sectionName.geometry.coords[2]
        #
        #Get list of files to plot section from, based on filename
        fileslist=[]
        for root, dirs, files in os.walk(folder,topdown=True):
            for name in files:
                fullpath=os.path.join(root,name)
                csvname,extension=name.split(".")
                if csvname==filename:
                    fileslist.append(fullpath)
                    
        #Calculate chainage and other values for data from same section, from all other files
        for file in fileslist:
            subfolder=os.path.basename(os.path.dirname(file))
            csv=pd.read_csv(file)
            rawData=pd.DataFrame(csv)
            #calculate chainage for each of the points, with O at point of minimum x
            ch=[]
            for i in range(len(rawData)):
                point=(rawData.iloc[i]['//X'],rawData.iloc[i]['Y'])
                chainage,offset=Project(centre,end,point)
                ch.append(chainage)
            rawData['distance']=ch
            rawData['distance']=rawData['distance'].fillna(0)
            
            #Roundup distances and RLto multiple of 0.1
            rawData['distance']=rawData['distance'].round(1)
            rawData['Z']=rawData['Z'].round(1)
            #Group rounded data
            grouped_multiple = rawData.groupby(['distance','Z']).agg({'Z':'mean'})
            grouped_multiple.columns = ['Z_mean']
            grouped_multiple = grouped_multiple.reset_index()
            sectionData=grouped_multiple
            #Read section id and year from folder and file name
            sectionData['sectionId']=[filename for i in range(len(sectionData))]
            sectionData['Year']=[str(subfolder) for i in range(len(sectionData))]
            dfObj=dfObj.append(sectionData)
    return dfObj
#
#
#Main Program
#get the current file directory and set relative path to other folders
scriptPath=pathlib.Path(__file__).parent.absolute()
centerLinePath=os.path.abspath(os.path.join(scriptPath,"../Outputs/Shapefiles"))
cloudFolder=os.path.abspath(os.path.join(scriptPath,"../Outputs/SectionsCloud"))

#Read Centerline
centerline=gpd.read_file(os.path.join(centerLinePath,"River_Centerline.shp"))
#Create Section Lines at 25 m interval and 20 m width
sections=createSectionLines(centerline,25,20)
#rename sections inside folder
renameFiles(cloudFolder,sections)
#Create sections from renamed section data
df=createData(sections, cloudFolder)         
#Create dynamic subplot
uniqueSectionId=df['sectionId'].unique()

categorical_vars = uniqueSectionId
num_plots = len(categorical_vars)+1
total_cols=2
total_rows = num_plots//total_cols + 1
fig,axs = plt.subplots(total_rows, ncols=total_cols,
                        figsize=(7*total_cols, 7*total_rows), constrained_layout=True)

for i, var in enumerate(categorical_vars):
    row = i//total_cols
    pos = i % total_cols
    print(i,var)
    sns.lineplot(x="distance", y="Z", hue="Year", estimator='mean',ci=None,lw=1,data=df[df['sectionId']==var],ax=axs[row][pos]).set_title('Change in section at {section}'.format(section=var))
    plt.axis('equal')
plt.show()

