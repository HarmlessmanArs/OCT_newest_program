# __OCT newest program__

# _What is this program for?_

This program was made for OCT images processing. It consits of different modules 
such as boundaries detection and calculation of their positions and distinations between them.
Additionaly this program allows to calculate average intensity and extinction corfficient in ROI. 
Also, it was made to calculate geometrical and optical parameters in diffusion process 

# _Structure of the program_

Program.py
* app - the heart of the program
    * init.py
    * main.py
* controllers - here are described how program responses to user 
    * init.py
    * widgets
      * init.py
      * widgets.py
      * gallery_controller.py
      * graph_controller.py
      * table_controller.py
      * imaing_av_int_controller.py
      * imaing_boundaries_controller.py
      * imaing_roi_controller.py
      * imaing_mu_t_controller.py
    * windows
      * init.py
      * main_window_controller.py
    * addtional_windows
      * init.py
      * addtional_windows_conroller.py
      * data_info_controller.py
* core - mathematical functions 
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
* gui - how windows look
  * init.py
  * windows
    * Different classes of windows
  * dialogs
    * Different classes for dialogs windows
  * additional_windows
    * Different classes for additional windows
* projects_storage - how to save, open or create project
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
* state - the state of datasets and project itself
  * project_state
    * init.py
    * constants.py
  * dataset_state
    * init.py
    * gallery_state.py
* utils 
  * init.py
  * link_base.py
  * logging.py
  * paths.py
* workers - functions which works on background not to block main window 
  * init.py

# _User path_

Program launch → Creation of a new gallery and, accordingly, a separate folder for the dataset → Loading and selecting images for processing → 
Using the ROI module to define the region of interest and detect the object boundaries within this region → 
Using the Boundaries module to obtain information about the boundary positions for subsequent thickness calculations → 
In the main window menu bar, there will either be an option to export data (with the ability to choose tables and other content) or 
to continue data processing.

There will also be an option to load existing projects and continue working within the loaded project.

# _Tasks (last updated 21.05.26)_

1) Change ~~QTableWidget~~ in table module to QTableView + QAbstractTableModel
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
3) В главном окне есть поле QTreeWidget, в котором хранится структура проект: папки, в котрых находятся различные виджеты.
Нужно сделать так, чтобы при выборе конкрентной папки отображались только виджеты, которые связаны только с ней (галереи,
таблицы, графики и т.д.)
4) В дополнении к прошлому пункту необходимо добавть такую важную функцию как удаление виджета, если его удалили из списка 
или, наоборот, удаление из списка при удалении виджета\
5) Получается, папка как сущность тоже должна иметь idx для того, чтобы к ней можно было обратиться и свзаться с ней виджеты.
Это должно помочь построить иерархию
