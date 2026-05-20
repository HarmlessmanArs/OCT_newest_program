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
* core
  * average_intensity_calculation.py
  * mu_t_calculation.py
  * boundaries_extraction.py
  * boundaries_calculation.py
* events
  * init.py
* gui
  * init.py
  * windows
    * Different classes of windows
* save_load_new
  * init.py
  * projects_storage
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
* services
* state
* utils
* workers

# Tasks (last updated 20.05.26)

1) Change QTableWidget in table module to QTableView + QAbstractTableModel
2) 