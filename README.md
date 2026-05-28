# __OCT newest program__

# CONTENT

1) What is this program for?
2) How to run the code
3) Structure of the program
4) User path
5) Tasks
6) Bugs

# _What is this program for?_

This program was made for OCT images processing. It consits of different modules 
such as boundaries detection and calculation of their positions and distinations between them.
Additionaly this program allows to calculate average intensity and extinction corfficient in ROI. 
Also, it was made to calculate geometrical and optical parameters in diffusion process

# __How to run the code__
### Python version
* Python 3.13
### Libraries you need
* numpy (2.4.6)
* cv2 (4.12.0.88)
* PyQt6 (6.11.0)
* pandas (2.3.3)
* scipy (1.17.1)
* zarr (3.1.2)

# _Structure of the program_

Program.py
* app - the heart of the program
    * init.py
    * main.py
* controllers - here are described how program responses to user 
    * init.py
    * small_controllers.py
    * workspace_controller.py
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
      * add_controllers
        * init.py
        * hierarchy_controller.py
        * project_io_controller.py
        * widget_factory_controller.py
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
    * init.py
    * ui_gallery_window.py
    * ui_graphic_window.py
    * ui_imaging_av_int_window.py
    * ui_imaging_boundaries_window.py
    * ui_imaging_mu_t_window.py
    * ui_imaging_roi_window.py
    * ui_main_window.py
    * ui_table_window.py
  * dialogs
    * init.py
  * additional_windows
    * init.py
    * ui_data_info.py
* projects_storage - how to save, open or create project
  * init.py
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
    * init.py
    * laz_array
* services - 
  * init.py
* state - the state of datasets and project itself
  * project_state
    * init.py
    * constants.py
    * state.py
    * runtime_registry
  * dataset_state
    * init.py
    * gallery_state.py
* utils 
  * init.py
  * link_base.py
  * logging.py
  * paths.py
  * types_restore.py
* workers - functions which works on background not to block main window 
  * init.py

# _User path_

Program launch → Creation of a new gallery and, accordingly, a separate folder for the dataset → Loading and selecting images for processing → 
Using the ROI module to define the region of interest and detect the object boundaries within this region → 
Using the Boundaries module to obtain information about the boundary positions for subsequent thickness calculations → 
In the main window menu bar, there will either be an option to export data (with the ability to choose tables and other content) or 
to continue data processing.

There will also be an option to load existing projects and continue working within the loaded project.

# _Tasks (last updated 28.05.26)_

1) Change ~~QTableWidget~~ in table module to QTableView + QAbstractTableModel
2) Write mathematical modules for (crossed text means this task has been done):
   1) ~~boundaries extraction~~ need changes in logic
   2) ~~boundaries calculation~~
   3) ~~average intensity~~
   4) roi calculation
   5) ~~mu_t calculation~~
   6) parameters calculation
      1) v1
      2) v2
      3) v3
3) В дополнении к прошлому пункту необходимо добавть такую важную функцию как удаление виджета, если его удалили из списка 
или, наоборот, удаление из списка при удалении виджета (выполнено чавстично, при удалении непоредственно виджета 
запись о нём остаётся в дереве)
4) Добить созранение и загрузку проекта (пока встречается такая проблема, что при загрузке проекта не подгружается состояние
проекта, а также все окна, которые были в "старом" проекте остаются)



# _Bags_
1) Если нет активных папок, то при создании галереи программа вылетает. Необходимо проверять, есть ли папка. В случае отсутствия
ничего не делать или выдать сообщение о том, что необходимо создать папку
2) 