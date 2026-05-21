# OCT newest program

# What is this program for?

This program was made for OCT images processing

# Structure of the program

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

# Tasks (last updated 20.05.26)

1) Change QTableWidget in table module to QTableView + QAbstractTableModel
2) Write mathematical modules for (crossed text means this task has been done):
   1) boundaries extraction
   2) boundaries calculation
   3) average intensity
   4) mu_t calculation
   5) parameters calculation
      1) v1
      2) v2
      3) v3