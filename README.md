# Python Sync OneDrive
Sync local files to OneDrive without adding them to OneDrive. Useful when you want to (one-way) sync a file to the cloud without changing its location locally.

## Usage
1. Git clone the repo.
2. Install requirements: `python -m pip install -r requirements.txt`
3. Adapt the main.py to provide the paths to the file to sync.
4. Add task to Windows Task Scheduler with `python-sync-onedrive.xml`. Adapt the account to execute the task from.
5. Save the task and start running it.
6. On first load, you need to login in to your OneDrive account following the steps shown in the powershell window.
7. Subsequently, login is not required unless the authentication token expires in which case you will be asked to repeat step 4.
