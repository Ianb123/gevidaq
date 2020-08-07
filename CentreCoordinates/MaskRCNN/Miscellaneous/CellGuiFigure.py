# -*- coding: utf-8 -*-
"""
Created on Wed Jul 22 20:31:41 2020

@author: meppenga
"""

 
import numpy as np
import os
from skimage.measure import find_contours
from matplotlib import patches
from matplotlib.patches import Polygon
import skimage.io
import random
import colorsys

from MaskRCNN.Engine.MaskRCNN import MaskRCNN as modellib
from MaskRCNN.Miscellaneous.utils import ConvertImage2RGB
from MaskRCNN.Miscellaneous.utils import resize, ReshapeMask2BBox
from MaskRCNN.Miscellaneous.utils import CreateFullMask as CreateFullMask_ut
from MaskRCNN.Miscellaneous.DrawnUI import DrawPolygons

class CellGuiFigureHandle(object):
    
    def __init__(self,config, fig, ax, enableDrawing=False):
        """This class creates the figure handle to display the results of a detection
        It uses Matplotlib as its backend for the figure, so input should be 
        matplotlib figrue and axis
        An example is on how to use this can be found in: MaskRCNN.Miscellaneous.ExampleGui
        Inputs:
            conif: a MaskRCNN config file
            fig: Canvas to draw on
            ax: axis to draw image on"""
        self.fig    = fig
        self.ax     = ax
        self.config = config
        # Use mask of size 28 by 28 (normal output maxk classifier)
        # used for fast computation, use ReshapeMask2BBox to reshape to box
        # coordiantes, or use CreateFullMask to reshape to image size
        self.config.RETURN_MINI_MASK = True 
        self.fig.canvas.mpl_connect('button_press_event', self.on_click)
        self.fig.canvas.mpl_connect('button_release_event', self.on_release)
        self.xy = (0,0)
        
        
        # Create MaskRCNN model
        self.Predictor = modellib(self.config, 'inference', model_dir=self.config.LogDir)
        self.Predictor.compileModel()
        self.Predictor.LoadWeigths(self.config.WeigthPath, by_name=True)
        
        # Create Figure
        self.Init_Figure()    
                
        # Detection and display options
        self.HighlightColor = (0.0, 1.0, 0.0)       # RGB  
        self.NumCells       = 0 # number of detected cells
        self.Radius         = 3 # radius centre coordinate
        self.EnableMultiCellSelection = True 
        self.AllSelectedIndex = [] # index of evry selected cell with respect to Results
        self.UsePartial       = [False, 2,2] # Split image in x parts y,x       
        self.UseRandomColor   = True # otherwise color class dependend
        self.CellTypeColor    = []
        self.CreatePolygons   = DrawPolygons(self.fig, self.ax, enableDrawing)
        self.CreatePolygons.On_PolygonCreation(self.On_PolygonCreation_Fcn)
        self.CreatePolygons.MovePolygonPoint.On_moved_Polygon(self.On_MovePolygonPoints)
        self.EnbaleSelectCell = not enableDrawing
        self.MovePolygonIndex = -1
        
        
        # Show default image
        try:
            self.ShowImage(skimage.io.imread(r'M:\tnw\ist\do\projects\Neurophotonics\Brinkslab\Data\Martijn\JSF_Example.jpg'))
        except:
            pass
     
    def resetDrawing(self,All=False):
        self.CreatePolygons.Reset(All)
    
    def nonfunc(self):
        pass
    
    def on_click(self,event):
        """Stores the x and y positon of the mouse when a mouse button is pressed"""
        self.xy = (event.xdata,event.ydata)

    def on_release(self,event):
        """Verifys, when a mouse button is released if the mouse is at the same 
        location as when the mouse button was pressed"""
        if not self.CreatePolygons.enable:
            if event.xdata == None or event.ydata == None:
                return
            if self.CreatePolygons.Compare_points(self.xy, (event.xdata,event.ydata)):
                self.on_Mouse_Click(event)
    
    def On_MovePolygonPoints(self):
        if self.MovePolygonIndex > -1:
            bbox, mask = self.CreatePolygons.CreateMaskFromPolygon(self.CreatePolygons.MovePolygonPoint.points)
            shapeMask  = np.shape(self.Results['masks'][:,:,0])
            mask = resize(mask, (shapeMask[0], shapeMask[1]))
            self.Results['masks'][:,:,self.MovePolygonIndex] = mask
            self.Results['rois'][self.MovePolygonIndex,:]    = bbox
            self.patches[self.MovePolygonIndex] =  self._CreateImageAtributes(self.MovePolygonIndex, self.HighlightColor)
            self.DisplayImage()
            self.CreatePolygons.MovePolygonPoint.Addpacthes()

    
    def MovePolygonPoints(self,index):
        self.MovePolygonIndex = index
        mask = self.Results['masks'][:,:,index]
        bbox = self.Results['rois'][index,:]
        mask = ReshapeMask2BBox(mask, bbox)
        padded_mask  = np.zeros((mask.shape[0] + 2, mask.shape[1] + 2), dtype=np.uint8)
        padded_mask[1:-1, 1:-1] = mask.astype(np.uint8)
        y1, x1, _, _ = bbox
        # find contours, flip from (y,x) to (x,y),  reduce number of points by filtering
        contours = find_contours(padded_mask, 0.5)
        # Find the polygon with the most number of points (tjis is propably the polygon of interest)
        find_polygon_index = 0
        num_elements = 0
        for ii in range(len(contours)):
            if contours[ii].shape[0] > num_elements:
                num_elements = contours[ii].shape[0]
                find_polygon_index = ii +0
            
        contours =  self.filter_contour_points(contours[find_polygon_index][:,::-1] )
        # transform from mask coordinates to image coordinates
        contours += (x1-1,y1-1)
        self.CreatePolygons.MovePolygonPoint.ChangePoints(contours)
        self.CreatePolygons.toggle_enable_MovePolygonPoint(True)
        
    def filter_contour_points(self,points):
        """This filter reduces the number of points from a selection of points
        The filter verifies if how close each point is to the next point in the array.
        If two  points are too close, then one of the points is remove:
            Input: array of points shape (N,2)
            Return: array of points shape (M,2)"""
        pointsout = np.zeros(np.shape(points),dtype=points.dtype)
        pointsout[0,:] = points[0,:]
        idx = 1
        for point in points[1:,:]:
            xdelta = abs(point[0] - pointsout[idx-1,0])
            ydelta = abs(point[1] - pointsout[idx-1,1])
            if xdelta > 4.0 or ydelta > 4.0:
                pointsout[idx,:] = point
                idx += 1
        return pointsout[:idx,:]
    
    def On_PolygonCreation_Fcn(self):
        bbox     = self.CreatePolygons.Bbox[-1]
        mask     = self.CreatePolygons.Mask[-1]
        labelOut = self.CreatePolygons.Names[-1]
        for idx, labels in enumerate(self.config.ValidLabels):
            label = idx+1
            if labelOut == labels:
                break
        color = (0.0, 0.0, 1.0) # RGB
        self.NumCells += 1
        try: 
            ResultsExist = True
            shapeMask  = np.shape(self.Results['masks'][:,:,0])
        except:
            ResultsExist = False
            shapeMask    = (28,28) 
            
        bboxArray  = np.zeros((self.NumCells,4),dtype=np.int32)
        maskArray  = np.zeros(shapeMask+(self.NumCells,),dtype=np.float32)
        labelArray = np.zeros(self.NumCells,dtype=np.int32)
        scoreArray = np.zeros(self.NumCells,np.float32)
        Centre_coorArray = np.zeros((self.NumCells,2),np.int32)
        
        # assign new values
        mask = resize(mask, (shapeMask[0], shapeMask[1]))
        bboxArray[-1,:]   = bbox
        maskArray[:,:,-1] = mask
        labelArray[-1]    = label
        scoreArray[-1]    =  1.0
        y1, x1, y2, x2 = bbox
        Centre_coorArray[-1,:] = (int((y2-y1)/2+y1), int((x2-x1)/2+x1))
        
        # copy old values
        if ResultsExist:         
            bboxArray[:-1,:]        = self.Results['rois']
            maskArray[:, :, :-1]    = self.Results['masks']
            labelArray[:-1]         = self.Results['class_ids']
            scoreArray[:-1]         = self.Results['scores']
            Centre_coorArray[:-1,:] = self.Results['Centre_coor']
            maskshape               = self.Results['maskshape']
            self.Colors.append(color)
        else:
            maskshape  = np.shape(self.Image)[0:2]
        self.AllSelectedIndex.append(self.NumCells-1)
        self.SelectedCellIndex = self.NumCells-1
        self.Results = {'rois':        bboxArray,
                        'class_ids':   labelArray,
                        'Centre_coor': Centre_coorArray,
                        'masks':       maskArray,
                        'scores':      scoreArray,
                        'maskshape': maskshape}
        if ResultsExist:
            self.patches.append(self._CreateImageAtributes(self.NumCells-1, self.HighlightColor))
        else:
            self.CreateImage()
        self.resetDrawing(True)
        self.DisplayImage()
        
    def Toggle_drawing(self,value=None):
        self.CreatePolygons.toggle_enable(value)
        self.CreatePolygons.toggle_enable_MovePolygonPoint(self.CreatePolygons.enable)
        self.EnbaleSelectCell = not self.CreatePolygons.enable
        if self.CreatePolygons.enable and self.MovePolygonIndex > -1:
            self.MovePolygonPoints(self.MovePolygonIndex)
        
     
    def getSelectedCellAtributes(self):
        if self.NumCells == 0:
            raise Exception('No cell instances, thus no selected cell results')
        class_names = ['BG'] + self.config.ValidLabels
        AllResults = {}
        for index in self.AllSelectedIndex:
            Result = {'rois':          self.Results['rois'][index],
                      'mask':          self.Results['masks'][:,:,index],
                      'class_ids':     self.Results['class_ids'][index],
                      'Centre_coor':   self.Results['Centre_coor'][index],
                      'Centre_coor x': self.Results['Centre_coor'][index][1],
                      'Centre_coor y': self.Results['Centre_coor'][index][0],
                      'Label':         class_names[self.Results['class_ids'][index]]}
            AllResults[str(index)] = Result
        return AllResults
    
    def toggleCellRandomColor(self, value=None):
        if value == None:
            self.UseRandomColor = not self.UseRandomColor
        else:
            self.UseRandomColor = value
        if not self.UseRandomColor and len(self.CellTypeColor) != (len(self.config.ValidLabels)+1):
            N = len(self.config.ValidLabels)+1
            brightness = 1.0 
            hsv = [(i / N, 1, brightness) for i in range(N)]
            colors = list(map(lambda c: colorsys.hsv_to_rgb(*c), hsv))
            self.CellTypeColor = colors
            
    def setCelltypeColor(self,color):
        color = [(1.0,0.0,0.)] + color
        self.CellTypeColor = color
    
    def getAllResults(self, event):
        if self.NumCells == 0:
            return {}, {}
        else:
            return self.Results, self.getSelectedCellAtributes()
    
    def getResults(self):
        """Returns a dict with all the results obtained from the inference run 
        on the image"""
        if self.NumCells == 0:
            return {}
        else:
            return self.Results
    
    def ChangeWeighs(self, file):
        """Change the weight file used for the detection"""
        self.config.WeigthPath =file
        self.Predictor.LoadWeigths(self.config.WeigthPath, by_name=True)
        
    def Init_Figure(self):       
        # Create Buttons axis
        self.fig_msg         = self.fig.text(0, 0.01,'Status: ')
        self.fig.text(0,0.01,'Brinks lab\nAuthor: Martijn Eppenga\nTensorFlow version: '+self.Predictor.TF_Version+'\n')
        self.Button_All_Label  = ['Show Cells','Show Mask', 'Show BBox', 'Show Label', 'Show centre']
        self.Button_High_Label = ['Show Cells','Show Mask', 'Show BBox', 'Show Label', 'Show centre']
        # Create state dicts
        self.Display_All_State = {}
        for label, state in zip(self.Button_All_Label, [True, False, False, False, False]):
            self.Display_All_State[label] = state
        self.Display_High_State = {}
        for label, state in zip(self.Button_High_Label, [True, True, True, False, True]):
            self.Display_High_State[label] = state
            
    def init_setButtonStates(self,button,state):
        """THis is an init function to overide the default states which indicate
        which aspect of which cells to show
        Input:
            button: str, All for all cells states, Select or High for selected cells
            state: list of bool, True if on, False if off must have the same lengh
                    as self.Button_All_Label or self.Button_High_Label"""
        if button == 'All':
            for label, state in zip(self.Button_All_Label, state):
                self.Display_All_State[label] = state
        elif button == 'Select' or button == 'High':
            for label, state in zip(self.Button_High_Label, state):
                self.Display_High_State[label] = state
            
    

        
    def on_click_All(self, StateList):
        """Callback which updates the figure when a checkbox setting is changed
        To display the change use the DisplayImage method"""
        for idx, state in enumerate(StateList):
            self.Display_All_State[self.Button_All_Label[idx]] = state
        
    
    def on_click_High(self, StateList):
        """Callback which updates the figure when a checkbox setting is changed
        To display the change use the DisplayImage method"""
        for idx, state in enumerate(StateList):
            self.Display_High_State[self.Button_High_Label[idx]] = state

    
    def on_Mouse_Click(self,event):
        """Callback which searches for a cell at the location in the figure where
        the user have clicked with his mouse.
        If a new cell is selected it will update the figure"""
        try:
            self.Results['masks'][0,0,0]
        except:
            return
        if self.NumCells > 0 and self.EnbaleSelectCell:
            if event.xdata == None or event.ydata == None:
                # ensure click is inside figure
                return
            elif event.xdata < 1.01 or event.ydata < 1.01:
                # ensure click is inside figure (not inside checkbox)
                return

            ShapeMask      = self.Results['maskshape']
            # get coorinates at selected location in image coordinates            
            xcoor = min(max(int(event.xdata),0),ShapeMask[1])
            ycoor = min(max(int(event.ydata),0),ShapeMask[0])
            Found, index = self.FindCellIndex(xcoor, ycoor)
            if Found:
                self.SelectedCellIndex = index
                self.MovePolygonIndex  = index+0
                # Check if a cell is selected
                if self.EnableMultiCellSelection:
                    if self.SelectedCellIndex in self.AllSelectedIndex:
                        # remove if clicked again on cell
                        self.patches[self.SelectedCellIndex]  = self._CreateImageAtributes(self.SelectedCellIndex, self.Colors[self.SelectedCellIndex])
                        self.AllSelectedIndex.remove(self.SelectedCellIndex)
                        self.DisplayImage()
                    else:
                        # add if fist time click
                        self.AllSelectedIndex.append(self.SelectedCellIndex)
                        self.patches[self.SelectedCellIndex] = self._CreateImageAtributes(self.SelectedCellIndex, self.HighlightColor) 
                        self.DisplayImage()
                elif self.SelectedCellIndex != self.indexPrev:
                    for index in self.AllSelectedIndex:
                        self.patches[index] = self._CreateImageAtributes(index, self.Colors[index])
                    self.patches[self.SelectedCellIndex] = self._CreateImageAtributes(self.SelectedCellIndex, self.HighlightColor)                     
                    self.AllSelectedIndex = [self.SelectedCellIndex+0]
                    self.DisplayImage()
                
    
    def FindCellIndex(self,x,y):
        """Finds the cell which includes the points x and y and returns the index 
        of this cell with respect to the Result array and a boolean True
        if no cells is foun returns a boolean False""" 
        Found = False
        for ii in range(self.NumCells):
            y1, x1, y2, x2 = self.Results['rois'][ii]
            if x >= x1  and x <= x2 and y >= y1 and y <= y2:
                Found = True
                break
        return Found, ii

    def CreateTitle(self):
        """Sets the title of the main figure"""
        if self.SelectedCellIndex == None:
            return
        class_names = ['BG'] + self.config.ValidLabels
        title = "Selected Cell: {} {:.3f}\n Centre: y = {:3d}, x = {:3d}\nTotal selected: {:03d}".format(
            class_names[self.Results['class_ids'][self.SelectedCellIndex]],
            self.Results['scores'][self.SelectedCellIndex],
            self.Results['Centre_coor'][self.SelectedCellIndex][0],
            self.Results['Centre_coor'][self.SelectedCellIndex][1],
            len(self.AllSelectedIndex))
        self.ax.set_title(title)
    
    def RunDetection(self,Image):
        """Runs a detection on an image
        Input:
            Image: str or array. If a string is given as input, then the function
                assumes that it is a file path. It will load the image and run 
                the detection on the image.
                If an array is given it is assuemd that the array is the image 
                and it will run the detection on the image"""
        # Check input
        self.Text_ChangeStatus('Parsing data')
        if isinstance(Image, str):
            # Load image
            if not os.path.isfile(Image):
                return
            Image = skimage.io.imread(Image)
        
        # Perapre image for detection
        Image = ConvertImage2RGB(Image)
        self.Image = Image
        # Run detection
        if self.UsePartial[0]:
            self.RunPartialDetection(self.Image)
        else:
            self.Text_ChangeStatus('Run detection')
            self.Results = self.Predictor.detect([Image])[0]
            self.Text_ChangeStatus('Run detection done')
        self.NumCells = len(self.Results['class_ids'])
        self.SelectedCellIndex = None
        self.indexPrev         = None
        self.AllSelectedIndex = []
        # Create and display figure
        height, width = self.Image.shape[:2]
        self.ax.set_xlim(-10, width + 10)
        self.ax.set_ylim(height + 10, -10)
        self.CreateImage()
        self.DisplayImage()
        self.MovePolygonIndex = -1

        
            
            
            
    def CreateImage(self):
        """Creates all atributes to display within the main figure"""
        if self.NumCells == 0:
            print("\n*** No instances to display *** \n")
            return
        self.Text_ChangeStatus('Create figure')
        self.CreateColors()
        self.patches = []
        for idx in range(self.NumCells):
            self.patches.append(self._CreateImageAtributes(idx,self.Colors[idx]))
        self.Text_ChangeStatus('Create figure done')
            
        
    def _CreateImageAtributes(self,Index,color): 
        """Create the atributes for a single cell
        Input:
            Index: int index coresponding to the cell for which the atributes are
                created (with respect to self.Results
             color: tuple (R,G,B) [0-1]: color to assign to each atribute"""
        if self.NumCells == 0:
            return [None,None,None,None,None,False]
        Mask        = self.Results['masks'][:,:,Index]
        Box         = self.Results['rois'][Index]
        score       = self.Results['scores'][Index]
        class_id    = self.Results['class_ids'][Index]
        class_names = ['BG'] + self.config.ValidLabels
        CCoor       = self.Results['Centre_coor'][Index]


        if not np.any(Box):
            return [None,None,None,None,None,False]
        
        y1, x1, y2, x2 = Box
        BoxPatches = patches.Rectangle((x1, y1), x2 - x1, y2 - y1, linewidth=2,
                            alpha=0.7, linestyle="dashed",
                            edgecolor=color, facecolor='none')
        CCoorPatches = patches.Circle(np.flipud(CCoor),radius=self.Radius, color='y')

        label   = class_names[class_id]
        caption = "{} {:.3f}".format(label, score) if score else label

        # padded image to create nice contour 
        Mask = ReshapeMask2BBox(Mask,Box)
        padded_mask = np.zeros(
                (Mask.shape[0] + 2, Mask.shape[1] + 2), dtype=np.uint8)
        padded_mask[1:-1, 1:-1] = Mask
        contours = find_contours(padded_mask, 0.5)
        vertsPatch = []
        for verts in contours:
            # Subtract the padding and flip (y, x) to (x, y) and add the
            # coordinate shift due to use of mini mask
            verts[:,:] = verts[:,::-1]  + (x1-1, y1-1)
            p     = Polygon(verts, facecolor="none", edgecolor=color)
            vertsPatch.append(p)
        return [BoxPatches, caption, vertsPatch, Box, CCoorPatches, True]
    
    def ShowImage(self,Image):
        """Mehtod to show an image without running the MaskRCNN inferrence on
        it"""
        self.ax.clear()
        self.ax.axis('off')
        self.ax.imshow(Image)
        self.Image = Image
        self.Results = {}
        self.NumCells = 0
        self.MovePolygonIndex = -1
        self.SelectedCellIndex = None
        self.indexPrev         = None
        self.AllSelectedIndex  = []
        self.Text_ChangeStatus('Display, no detection')
        height, width = Image.shape[:2]
        self.UpdateFigure()
        
    
    def DisplayImage(self):
        """Displays the main image in the figure"""
        ax_limits = [self.ax.get_xlim(), self.ax.get_ylim()]
        Masked_Image = self.Image.copy()
        if self.NumCells == 0:
            self.ax.imshow(Masked_Image.astype(self.Image.dtype))
            self.Text_ChangeStatus('Display image done')
            self.UpdateFigure()
            return
        self.Text_ChangeStatus('Display image')
        #Clear axis and set border limits +10 pixels for nice view
        self.ax.clear()
        height, width = self.Image.shape[:2]
        self.ax.set_ylim(height + 10, -10)
        self.ax.set_xlim(-10, width + 10)
        self.ax.axis('off')
        for index, atribute in enumerate(self.patches):
            if not atribute[-1]:
                # no patches, go to next item
                continue          
            if index in self.AllSelectedIndex:
                CheckBoxSatus = self.Display_High_State
                color = self.HighlightColor
            else:
                CheckBoxSatus = self.Display_All_State
                color = self.Colors[index]
            if CheckBoxSatus['Show Cells']:
                for patch_ in atribute[2]:
                    self.ax.add_patch(patch_) 
            else:
                continue
            if CheckBoxSatus['Show Mask']:
                # Masked_Image = self.apply_mask(Masked_Image, self.Results['masks'][:,:,index], color)
                Masked_Image = self.apply_mask_Fast(Masked_Image, self.Results['masks'][:,:,index], atribute[3], color)
            if CheckBoxSatus['Show BBox']:
                self.ax.add_patch(atribute[0])
            if CheckBoxSatus['Show Label']:
                y1, x1, y2, x2 = atribute[3]
                self.ax.text(x1, y1 + 8, atribute[1],
                        color='w', size=11, backgroundcolor="none")
            if CheckBoxSatus['Show centre']:
                self.ax.add_patch(atribute[4])
        self.ax.imshow(Masked_Image.astype(self.Image.dtype)) 
        self.CreateTitle()
        self.Text_ChangeStatus('Display image done')
        self.ax.set_xlim(ax_limits[0])
        self.ax.set_ylim(ax_limits[1])
        self.UpdateFigure()
        
    def Text_ChangeStatus(self,msg):
        """Updates the satus message
        Input: str, message to display"""
        self.fig_msg.set_text('Status: '+msg)
        self.UpdateFigure()
        

    def UpdateFigure(self):   
        """Update figure, can be used to force matplotlib to immediately update
        the figure"""
        self.fig.canvas.draw()
        self.fig.canvas.flush_events()         

  
    def CreateColors(self, bright=True):
        """
        Generate random colors.
        To get visually distinct colors, generate them in HSV space then
        convert to RGB.
        """
        N = self.NumCells
        if self.UseRandomColor:
            brightness = 1.0 if bright else 0.7
            hsv = [(i / N, 1, brightness) for i in range(N)]
            colors = list(map(lambda c: colorsys.hsv_to_rgb(*c), hsv))
            random.shuffle(colors)
        else:
            colors = []
            for ii in range(N):
                colors.append(self.CellTypeColor[self.Results['class_ids'][ii]])
        self.Colors = colors
    
        
    def apply_mask_Fast(self,image, mask, bbox, color, alpha=0.5):
        """Apply the given mask to the image.
        This method is a speed up of the apply_mask method
        By using the bounding boxes one can filter out many zero calculations
        Specially powerful for large images with small cells
        """
        # Get bbox indices and padded it one pixel to ensure proper mask generation
        mask = ReshapeMask2BBox(mask, bbox)
        y1, x1, y2, x2 = bbox

        # Apply mask
        for c in range(3):
            temp = image[y1:y2, x1:x2, c]
            temp[mask] = (temp[mask] * (1 - alpha) + alpha * color[c] * 255).astype(image.dtype)
            image[y1:y2, x1:x2, c] = temp
        return image
        

    def RunPartialDetection(self,Image):
        """Splits the image into several parts, runs detection on each part and
        combines the results This method is still in an aplha version"""
        ysplit, xsplit = self.UsePartial[1:3]
        ImageShape = np.shape(Image)
        if len(ImageShape) == 3:
            Image = Image[:,:,0]
        xrange = int(ImageShape[1]/xsplit)
        yrange = int(ImageShape[0]/ysplit)
        count = 0
        ImagePart = np.zeros((yrange,xrange),dtype=Image.dtype)
        Results = []
        num = ysplit*xsplit
        for idy in range(ysplit):
            for idx in range(xsplit):
                self.Text_ChangeStatus('Run detection part %d out of %d' % (count+1, num))
                coordinateTransform = [yrange * idy, xrange * idx]
                ImagePart[:,:] = Image[(yrange * idy):(yrange * (idy+1)), (xrange * idx):(xrange * (idx+1))]
                Results.append(self.transformResults(self.Predictor.detect([ImagePart])[0], coordinateTransform))             
                count += 1
        self.CreateResultsTransform(Results, np.shape(Image)[0:2])
        self.Text_ChangeStatus('Run detection done')
        self.DisplayImage()
    
    def transformResults(self, Results, transfrom):
        """Transfrom the coorinates from a partial detection back to the orginal
        image coordinates"""
        Results['rois'][:,(0,2)] += transfrom[0]
        Results['rois'][:,(1,3)] += transfrom[1]
        Results['Centre_coor'][:,(0)] += transfrom[0]
        Results['Centre_coor'][:,(1)] += transfrom[1]
        return Results



    def CreateFullMask(self, mask, bbox, maskshape=None):
        """Creates the full mask at image size from an input mask
        This can be either a raw output of the maskRCNN algorithm or a
        already resized to boxed sized mask"""
        if maskshape == None:
            maskshape = self.Results['maskshape']
        return CreateFullMask_ut(mask, bbox, maskshape)
        

    def CreateResultsTransform(self, Results, maskshape):
        """Creates the Result dictonary for a partial detection by combining 
        the results of a partial detection"""
        self.NumCells = 0
        for ii in range(len(Results)):
            self.NumCells += len(Results[ii]['class_ids'])
        rois        = np.zeros((self.NumCells,4),dtype=Results[0]['rois'].dtype)
        class_ids   = np.zeros(self.NumCells,dtype=Results[0]['class_ids'].dtype)
        Centre_coor = np.zeros((self.NumCells,2),dtype=Results[0]['Centre_coor'].dtype)
        masks       = np.zeros(np.shape(Results[0]['masks'])[0:2]+(self.NumCells,),dtype=Results[0]['masks'].dtype )
        scores      = np.zeros(self.NumCells,dtype=Results[0]['scores'].dtype)
        index = 0
        for ii in range(len(Results)):
            numcells                      = len(Results[ii]['class_ids'])
            endindex = index + numcells
            rois[index:endindex,:]        = Results[ii]['rois']
            class_ids[index:endindex]     = Results[ii]['class_ids']
            Centre_coor[index:endindex,:] = Results[ii]['Centre_coor']
            masks[:,:,index:endindex]     = Results[ii]['masks']
            scores[index:endindex]        = Results[ii]['scores']
            index = endindex+0
        self.Results = {'rois':        rois,
                        'class_ids':   class_ids,
                        'Centre_coor': Centre_coor,
                        'masks':       masks,
                        'scores':      scores,
                        'maskshape': maskshape}
    
 
    
    
    
    
    
    