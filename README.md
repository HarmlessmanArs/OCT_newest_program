# __OCT newest program__

# CONTENT

1) What is this program for?
2) How to run the code
3) Structure of the program
4) User path
5) Tasks
6) Bugs

# 1._What is this program for?_

This program was made for OCT images processing. It consits of different modules 
such as boundaries detection and calculation of their positions and distinations between them.
Additionaly this program allows to calculate average intensity and extinction corfficient in ROI. 
Also, it was made to calculate geometrical and optical parameters in diffusion process

# 2.__How to run the code__
### Python version
* Python 3.13
### Libraries you need
* numpy (2.4.6)
* cv2 (4.12.0.88)
* PyQt6 (6.11.0)
* pandas (2.3.3)
* scipy (1.17.1)
* zarr (3.1.2)

# 3._Structure of the program_

Program.py
* app - **Application core**
    * init.py
    * main.py: The primary entry point of the software. It instantiates the QApplication, initializes global services 
(logging, configuration), boots up the ProjectState, binds controllers, mounts the main window, and starts the Qt event 
loop.
* controllers - **User Interaction & Business Logic** 
    * init.py
    * small_controllers.py: Handles isolated, low-level UI components such as status bars, toolbars, and context tooltips.
    * workspace_controller.py: Orchestrates the Multi-Document Interface (MDI) area, coordinating the lifecycles, visibility, and focus of active window sheets.
    * widgets: MDI Document View Controllers
      * init.py
      * widgets.py
      * gallery_controller.py
      * graph_controller.py
      * table_controller.py
      * imaing_av_int_controller.py
      * imaing_boundaries_controller.py
      * imaing_roi_controller.py
      * imaing_mu_t_controller.py
    * windows: Global Application Windows
      * init.py
      * main_window_controller.py: Drives the main shell—menus, global shortcut key bindings, and sub-controller routing
      * add_controllers: Core Framework Services
        * init.py
        * hierarchy_controller.py: Drives the main project tree view (QTreeView), parsing item clicks and selection transitions
        * project_io_controller.py: Intercepts file actions (New, Open, Save, Save As) and communicates with background worker threads
        * widget_factory_controller.py: Implements the Factory Pattern. Reconstructs dynamic UI components at runtime from declarative serialized window descriptors
        * interface_controller.py:
    * addtional_windows: Different mini-windows
      * init.py
      * addtional_windows_conroller.py
      * data_info_controller.py
* core: **Mathematical & Algorithmic Domain**  
Pure Python/NumPy/SciPy engine. Contains zero references to PyQt dependencies, allowing these modules to be unit-tested or run independently via CLI scripts.
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
* events: **System Event Bus (empty)**
  * init.py
* gui: **Presentation Layer / Views**  
Contains layout layouts and structural visual configurations. These scripts omit functional execution patterns and focus entirely on assembling widgets into QLayout trees.
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
* projects_storage: **Project Virtual File System**  
Handles data serialization routines into efficient archival targets (e.g., compressed directory structures, HDF5, or Zarr archives
  * init.py
  * core: Logical representations of saved structures in system memory (It is not used still - empty)
    * init.py
    * datablock.py
    * dataset.py
    * handles.py
    * project.py
  * io: Low-level stream readers and writers 
    * init.py
    * loader.py: Asynchronous task execution workers (QThread) that process heavy disk operations while feeding real-time progress indicators back to the UI thread.
    * reader.py: File system handlers that perform block read operations against binary files or Zarr hierarchies
    * saver.py: Asynchronous task execution workers (QThread) that process heavy disk operations while feeding real-time progress indicators back to the UI thread.
    * writer.py: File system handlers that perform block write operations against binary files or Zarr hierarchies
  * lazy: 
    * init.py
    * laz_array: Virtual array proxy classes. Enables smooth UI handling of multi-gigabyte datasets by retrieving only the visible image slice on demand instead of loading the entire block into memory.
* services: **Cross-Cutting Application Concerns(empty)**
  * init.py
* state: **Centralized Application State**  
Keeps state snapshots sync-locked. Any interactive state shift (e.g., editing contrast limits or shifting active table selections) writes directly to this layer, automatically propagating updates out to registered view modules
  * project_state: Global runtime context
    * init.py
    * constants.py: Global application lookup references (lookup tables, color maps, ...).
    * state.py: The ProjectState manager—retains path addresses, flags unsaved changes (is_modified), and links active data matrices
    * runtime_registry: Keeps track of open MDI views and their matching controllers to cleanly close workspaces and prevent memory leaks
  * dataset_state
    * init.py
    * gallery_state.py: Tracks **localized** display configurations for image canvases
* utils: 
  * init.py
  * link_base.py: Abstract tools for structural linking and safe memory reference strategies
  * logging.py: Configures multi-destination diagnostic streams (empty)
  * paths.py: Abstracts platform-specific environment destinations
  * types_restore.py: Type-casting utility scripts to map basic JSON primitives back to native Python types and complex NumPy arrays during project loading
* workers: **Asynchronous Thread Pool Management (empty)** 
  * init.py

# 4._User path_

Program launch → Creation of a new gallery and, accordingly, a separate folder for the dataset → Loading and selecting images for processing → 
Using the ROI module to define the region of interest and detect the object boundaries within this region → 
Using the Boundaries module to obtain information about the boundary positions for subsequent thickness calculations → 
In the main window menu bar, there will either be an option to export data (with the ability to choose tables and other content) or 
to continue data processing.

There will also be an option to load existing projects and continue working within the loaded project.

# 5._Tasks (last updated 29.05.26)_

1) Выбор нескольких изображений
2) Удаление изображений (задача сложная, так как такое удаление должно полностью стираться из проекта/датасета)
2) Change ~~QTableWidget~~ in table module to QTableView + QAbstractTableModel
3) Write mathematical modules for (crossed text means this task has been done):
   1) ~~boundaries extraction~~ need changes in logic
   2) ~~boundaries calculation~~
   3) ~~average intensity~~
   4) roi calculation
   5) ~~mu_t calculation~~
   6) parameters calculation
      1) v1
      2) v2
      3) v3


# 6._Bags (last updated 31.05.26)_
1) Data and shape parameters при сохранении