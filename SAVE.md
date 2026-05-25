# __Here is a structure of project storage__

Project (.bmip)
* General information about project
* datablock_1
  * metadata (any unformation we need to know about)
  * data_information (pixel size, object features, etc)
  * original images
    * image_1 (name of the image)
    * image_2
    * ...
  * boundaries images
    * image_1 (name of the image)
    * image_2
    * ...
  * mu_t images
    * image_1 (name of the image), here is .txt format
    * image_2
    * ...
  * tables
    * table_1 (name of the table)
    * table_2
    * ...
  * graphs
    * graph_1 (name of the graph)
    * graph_2
    * ...
  * hidden data (as an example)
    * boundaries list of lists
    * mu_t list of np.ndarray
    * av_int list of np.ndarray
  * parameter calculation
    * non-array parameters
    * array parameters (it could be different for 2D, 3D and mapping cases)
      * ...
* datablock_2
  * ...
* datablock_3
  * ...

I think any object should be saved with it idx and linked to restore whole project correctly

# __About input data__
1) Images can be in different formats: .tiff, .png, .jpg and .bmp, but we need to be ready to expand this list
2) Object features are entered by user (Data info window, maybe there will be other windows)