# __OCT newest program__

# _What is this program for?_

This program was made for OCT images processing. It consits of different modules 
such as boundaries detection and calculation of their positions and distinations between them.
Additionaly this program allows to calculate average intensity and extinction corfficient in ROI. 
Also, it was made to calculate geometrical and optical parameters in diffusion process 

# _Structure of the program_

Program.py
* app - 
    * init.py
    * main.py
* controllers - 
    * init.py
    * widgets
      * init.py
      * widgets.py
      * gallery_window.py
    * windows
      * init.py
      * main_window.py
* core - 
  * roi_calculation.py
  * average_intensity_calculation.py
  * mu_t_calculation.py
  * boundaries_extraction.py
  * boundaries_calculation.py
  * parameters_calculation
    * init.py
    * v1_only_nondeformable.py
    * v2_only_deformable.py
    * v3_fusion.py
* events -
  * init.py
* gui -
  * init.py
  * windows
    * Different classes of windows
  * dialogs
    * Different classes for dialogs windows
* projects_storage - 
  * init.py
  * registory.py
  * core
    * init.py
    * datablock.py
    * dataset.py
    * handles.py
    * project.py
  * io
    * init.py
    * loader.py
    * reader.py
    * saver.py
    * writer.py
  * lazy
  * modules
* services - 
  * init.py
* state - 
  * project_state
    * init.py
    * constants.py
  * dataset_state
    * init.py
    * gallery_state.py
* utils - 
  * init.py
  * link_base.py
  * logging.py
  * paths.py
* workers - 
  * init.py

# _User path_



# _Tasks (last updated 21.05.26)_

1) Change QTableWidget in table module to QTableView + QAbstractTableModel
2) Write mathematical modules for (crossed text means this task has been done):
   1) ~~boundaries extraction~~
   2) ~~boundaries calculation~~
   3) ~~average intensity~~
   4) roi calculation
   5) ~~mu_t calculation~~
   6) parameters calculation
      1) v1
      2) v2
      3) v3