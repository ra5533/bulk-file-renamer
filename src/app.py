import os
import shutil
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import json
import threading
import time

class SimpleFileRenamer:
    def __init__(self, root):
        self.root = root
        self.root.title("File Renamer")
        self.root.geometry("1000x620")
        self.root.minsize(1000, 620)
        self.root.resizable(False, False)

        self.input_dir = None
        self.output_dir = None
        self.undo_stack = []
        self.redo_stack = []
        self.is_renaming = False
        self.stop_rename = False
        self.overwrite_all = False

        self.setup_style()
        self.create_ui()
        
        self.load_settings()
        
        self.root.bind("<Control-o>", lambda e: self.browse_input())
        self.root.bind("<Control-s>", lambda e: self.rename())
        self.root.bind("<F5>", lambda e: self.load_files())
        self.root.bind("<Delete>", lambda e: self.clear_selected())
        self.root.bind("<Control-z>", lambda e: self.undo_action())
        self.root.bind("<Control-y>", lambda e: self.redo_action())
        
        self.tree.bind("<Control-v>", self.paste_names)
        self.tree.bind("<Control-V>", self.paste_names)
        self.tree.bind("<Enter>", self._bind_mousewheel)
        self.tree.bind("<Leave>", self._unbind_mousewheel)

    def setup_style(self):
        style = ttk.Style()
        style.theme_use("default")

        style.configure(
            "Custom.Treeview",
            rowheight=28,
            borderwidth=1,
            relief="solid",
            background="white",
            fieldbackground="white"
        )

        style.map(
            "Custom.Treeview",
            background=[("selected", "#e6f3ff")],
            foreground=[("selected", "black")]
        )

        style.configure(
            "Custom.Treeview.Heading",
            font=("Segoe UI", 10, "bold"),
            relief="solid",
            borderwidth=1
        )

    def create_ui(self):
        top = tk.Frame(self.root, padx=20, pady=10)
        top.pack(fill="x")

        tk.Label(top, text="Input Folder", width=15, anchor="w").grid(row=0, column=0)
        self.in_entry = tk.Entry(top, width=75)
        self.in_entry.grid(row=0, column=1, padx=10)
        tk.Button(top, text="Browse", width=12, height=1,
                  command=self.browse_input).grid(row=0, column=2)

        tk.Label(top, text="Output Folder", width=15, anchor="w").grid(row=1, column=0, pady=10)
        self.out_entry = tk.Entry(top, width=75)
        self.out_entry.grid(row=1, column=1, padx=10)
        tk.Button(top, text="Browse", width=12, height=1,
                  command=self.browse_output).grid(row=1, column=2)

        count_frame = tk.Frame(self.root)
        count_frame.pack(fill="x", padx=20, pady=(5, 5))
        
        self.count_label = tk.Label(
            count_frame,
            text="Total Files : 0",
            font=("Segoe UI", 10, "bold"),
            anchor="w"
        )
        self.count_label.pack(side="left", fill="x", expand=True)
        
        self.progress_label = tk.Label(
            count_frame,
            text="Progress: 0/0 (0%)",
            font=("Segoe UI", 10),
            anchor="e",
            fg="blue"
        )
        self.progress_label.pack(side="right", fill="x")

        self.progress_frame = tk.Frame(self.root, height=8, bg="#e0e0e0")
        self.progress_frame.pack(fill="x", padx=20, pady=(0, 5))
        self.progress_frame.pack_propagate(False)
        
        self.progress_bar = tk.Canvas(self.progress_frame, bg="#f0f0f0", highlightthickness=0, height=8)
        self.progress_bar.pack(fill="both", expand=True)
        self.progress_indicator = self.progress_bar.create_rectangle(0, 0, 0, 8, fill="#4CAF50", width=0)

        self.progress_details = tk.Label(
            self.root,
            text="Ready",
            font=("Segoe UI", 9),
            anchor="w",
            padx=20,
            fg="gray"
        )
        self.progress_details.pack(fill="x")

        mid = tk.LabelFrame(
            self.root,
            text="Files",
            padx=5,
            pady=5,
            relief="solid",
            bd=1,
            height=350
        )
        mid.pack(fill="x", padx=20, pady=(5, 5))
        mid.pack_propagate(False)

        table_frame = tk.Frame(mid)
        table_frame.pack(fill="both", expand=True)

        scrollbar = ttk.Scrollbar(table_frame, orient="vertical")
        scrollbar.pack(side="right", fill="y")

        columns = ("original", "new", "status")
        self.tree = ttk.Treeview(
            table_frame,
            columns=columns,
            show="headings",
            style="Custom.Treeview",
            yscrollcommand=scrollbar.set
        )

        self.tree.heading("original", text="Original File")
        self.tree.heading("new", text="New Name (Paste / Click to Edit)")
        self.tree.heading("status", text="Status")

        self.tree.column("original", width=320)
        self.tree.column("new", width=320)
        self.tree.column("status", width=150, anchor="center")

        self.tree.tag_configure('pending', foreground='gray')
        self.tree.tag_configure('ready', foreground='blue')
        self.tree.tag_configure('done', foreground='green')
        self.tree.tag_configure('error', foreground='red')
        self.tree.tag_configure('skipped', foreground='orange')

        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar.config(command=self.tree.yview)

        self.tree.bind("<Button-1>", self.select_row_only)
        self.tree.bind("<Double-1>", self.edit_cell)

        bottom = tk.Frame(self.root, pady=15)
        bottom.pack(fill="x", padx=20)

        btn_opts = {"width": 16, "height": 1}

        tk.Button(bottom, text="Load Files",
                  command=self.load_files, **btn_opts).pack(side="left", padx=5)

        self.rename_btn = tk.Button(bottom, text="Start Rename",
                  command=self.rename, **btn_opts)
        self.rename_btn.pack(side="left", padx=5)

        tk.Button(bottom, text="Clear All",
                  command=self.clear, **btn_opts).pack(side="left", padx=5)
        
        self.stop_btn = tk.Button(bottom, text="⏹️ Stop", width=12, height=1,
                                 command=self.stop_renaming, fg="red")
        
        tk.Button(bottom, text="Undo (Ctrl+Z)", width=12,
                  command=self.undo_action).pack(side="right", padx=5)
        tk.Button(bottom, text="Redo (Ctrl+Y)", width=12,
                  command=self.redo_action).pack(side="right", padx=5)

    def update_progress(self, current=0, total=0, done=0, errors=0, skipped=0, current_file=""):
        if total > 0:
            percentage = (current / total) * 100
            
            width = self.progress_frame.winfo_width()
            if width > 0:
                progress_width = (current / total) * width
                self.progress_bar.coords(self.progress_indicator, 0, 0, progress_width, 8)
            
            progress_text = f"Progress: {current}/{total} ({percentage:.1f}%)"
            if done > 0 or errors > 0 or skipped > 0:
                progress_text += f" | ✓ {done} | ✗ {errors} | ⏭️ {skipped}"
            
            self.progress_label.config(text=progress_text)
            
            if current_file:
                details = f"Processing: {current_file}"
                if len(details) > 40:
                    details = f"Processing: ...{current_file[-35:]}"
                self.progress_details.config(text=details, fg="blue")
            else:
                self.progress_details.config(text="Ready", fg="gray")
            
            if percentage < 30:
                color = "#FF5252"
            elif percentage < 70:
                color = "#FFC107"
            else:
                color = "#4CAF50"
            
            self.progress_bar.itemconfig(self.progress_indicator, fill=color)
        else:
            self.progress_label.config(text="Progress: 0/0 (0%)")
            self.progress_bar.coords(self.progress_indicator, 0, 0, 0, 8)
            self.progress_details.config(text="Ready", fg="gray")

    def reset_progress(self):
        self.update_progress(0, 0, 0, 0, 0, "")

    def browse_input(self):
        path = filedialog.askdirectory()
        if path:
            self.input_dir = path
            self.in_entry.delete(0, tk.END)
            self.in_entry.insert(0, path)
            self.save_settings()

    def browse_output(self):
        path = filedialog.askdirectory()
        if path:
            self.output_dir = path
            self.out_entry.delete(0, tk.END)
            self.out_entry.insert(0, path)
            self.save_settings()

    def load_files(self):
        if not self.input_dir:
            messagebox.showerror("Error", "Input folder select karo")
            return

        self.tree.delete(*self.tree.get_children())
        self.reset_progress()

        try:
            files = [
                f for f in sorted(os.listdir(self.input_dir))
                if os.path.isfile(os.path.join(self.input_dir, f))
            ]
        except Exception as e:
            messagebox.showerror("Error", f"Cannot read folder: {str(e)}")
            return

        for f in files:
            try:
                file_path = os.path.join(self.input_dir, f)
                size = os.path.getsize(file_path)
                size_str = self.human_readable_size(size)
                self.tree.insert("", "end", values=(f, f, f"Pending ({size_str})"), tags=('pending',))
            except:
                self.tree.insert("", "end", values=(f, f, "Pending"), tags=('pending',))

        self.count_label.config(text=f"Total Files : {len(files)}")
        self.update_progress(0, len(files), 0, 0, 0, f"Loaded {len(files)} files")

    def rename(self):
        if self.is_renaming:
            return
            
        if not self.output_dir:
            messagebox.showerror("Error", "Output folder select karo")
            return

        items = self.tree.get_children()
        total = len(items)
        named = sum(1 for i in items if self.tree.item(i)["values"][1].strip())

        if total == 0:
            messagebox.showwarning("Warning", "Koi file nahi hai!")
            return

        if named < total:
            if not messagebox.askyesno(
                "Mismatch Warning",
                f"Total Files : {total}\nNew Names : {named}\n\nContinue?"
            ):
                return

        self.overwrite_all = False
        
        self.is_renaming = True
        self.stop_rename = False
        self.rename_btn.config(state="disabled")
        self.stop_btn.pack(side="left", padx=5)
        
        rename_thread = threading.Thread(target=self._rename_thread, args=(items, total))
        rename_thread.daemon = True
        rename_thread.start()

    def _rename_thread(self, items, total):
        success_count = 0
        error_count = 0
        skipped_count = 0
        
        self.root.after(0, lambda: self.update_progress(0, total, 0, 0, 0, "Starting..."))
        
        for idx, item in enumerate(items):
            if self.stop_rename:
                break
                
            current_file = self.tree.item(item)["values"][0]
            self.root.after(0, lambda idx=idx, file=current_file: 
                self.update_progress(idx+1, total, success_count, error_count, skipped_count, file))
            
            orig, new, _ = self.tree.item(item)["values"]

            if not new.strip():
                self.root.after(0, lambda item=item: (
                    self.tree.set(item, "status", "⏭️ Skipped"),
                    self.tree.item(item, tags=('skipped',))
                ))
                skipped_count += 1
                continue

            is_valid, error_msg = self.validate_filename(new)
            if not is_valid:
                self.root.after(0, lambda item=item, msg=error_msg: (
                    self.tree.set(item, "status", f"✗ {msg[:15]}..."),
                    self.tree.item(item, tags=('error',))
                ))
                error_count += 1
                continue

            src = os.path.join(self.input_dir, orig)
            dst = os.path.join(self.output_dir, new)

            if os.path.exists(dst):
                if not self.overwrite_all:
                    response = self._ask_overwrite_in_main_thread(new, src, dst)
                    
                    if response == "cancel":
                        self.stop_rename = True
                        break
                    elif response == "skip":
                        self.root.after(0, lambda item=item: (
                            self.tree.set(item, "status", "⏭️ Skipped"),
                            self.tree.item(item, tags=('skipped',))
                        ))
                        skipped_count += 1
                        continue
                    elif response == "overwrite_all":
                        self.overwrite_all = True
                    elif response == "skip_all":
                        self.root.after(0, lambda item=item: (
                            self.tree.set(item, "status", "⏭️ Skipped"),
                            self.tree.item(item, tags=('skipped',))
                        ))
                        skipped_count += 1
                        continue

            try:
                shutil.copy2(src, dst)
                self.root.after(0, lambda item=item: (
                    self.tree.set(item, "status", "✓ Done"),
                    self.tree.item(item, tags=('done',))
                ))
                success_count += 1
            except Exception as e:
                self.root.after(0, lambda item=item, e=str(e): (
                    self.tree.set(item, "status", f"✗ {str(e)[:15]}..."),
                    self.tree.item(item, tags=('error',))
                ))
                error_count += 1
            
            time.sleep(0.01)

        self.root.after(0, lambda: self._rename_complete(success_count, error_count, skipped_count, total))

    def _ask_overwrite_in_main_thread(self, filename, src, dst):
        import queue
        result_queue = queue.Queue()
        
        def show_dialog():
            dialog = tk.Toplevel(self.root)
            dialog.title("File Already Exists")
            dialog.geometry("500x250")
            dialog.transient(self.root)
            dialog.grab_set()
            
            dialog.update_idletasks()
            x = self.root.winfo_x() + (self.root.winfo_width() - dialog.winfo_width()) // 2
            y = self.root.winfo_y() + (self.root.winfo_height() - dialog.winfo_height()) // 2
            dialog.geometry(f"+{x}+{y}")
            
            tk.Label(dialog, text=f"File already exists:", 
                    font=("Segoe UI", 10, "bold")).pack(pady=(10, 5))
            
            tk.Label(dialog, text=filename, 
                    font=("Segoe UI", 9), fg="blue").pack(pady=(0, 10))
            
            info_frame = tk.Frame(dialog)
            info_frame.pack(pady=(0, 15), padx=20, fill="x")
            
            src_size = os.path.getsize(src)
            dst_size = os.path.getsize(dst) if os.path.exists(dst) else 0
            
            tk.Label(info_frame, text=f"Source: {self.human_readable_size(src_size)}", 
                    anchor="w").pack(fill="x")
            tk.Label(info_frame, text=f"Destination: {self.human_readable_size(dst_size)}", 
                    anchor="w").pack(fill="x")
            
            tk.Label(dialog, text="What do you want to do?", 
                    font=("Segoe UI", 9)).pack(pady=(0, 10))
            
            btn_frame = tk.Frame(dialog)
            btn_frame.pack(pady=(0, 10))
            
            def set_result(result):
                result_queue.put(result)
                dialog.destroy()
            
            row1 = tk.Frame(btn_frame)
            row1.pack(pady=5)
            
            tk.Button(row1, text="Overwrite", width=15,
                     command=lambda: set_result("overwrite")).pack(side="left", padx=5)
            tk.Button(row1, text="Skip", width=15,
                     command=lambda: set_result("skip")).pack(side="left", padx=5)
            
            row2 = tk.Frame(btn_frame)
            row2.pack(pady=5)
            
            tk.Button(row2, text="Overwrite All", width=15,
                     command=lambda: set_result("overwrite_all"), fg="green").pack(side="left", padx=5)
            tk.Button(row2, text="Skip All", width=15,
                     command=lambda: set_result("skip_all"), fg="orange").pack(side="left", padx=5)
            
            row3 = tk.Frame(btn_frame)
            row3.pack(pady=5)
            
            tk.Button(row3, text="Cancel All", width=32,
                     command=lambda: set_result("cancel"), fg="red").pack()
            
            def on_closing():
                set_result("skip")
            
            dialog.protocol("WM_DELETE_WINDOW", on_closing)
        
        self.root.after(0, show_dialog)
        
        return result_queue.get()

    def _rename_complete(self, success, errors, skipped, total):
        self.is_renaming = False
        self.rename_btn.config(state="normal")
        self.stop_btn.pack_forget()
        
        if self.stop_rename:
            self.update_progress(total, total, success, errors, skipped, "Stopped by user")
            messagebox.showinfo("Stopped", f"Renaming stopped!\n✓ {success} | ✗ {errors} | ⏭️ {skipped}")
        else:
            self.update_progress(total, total, success, errors, skipped, "Completed!")
            
            result_text = f"Completed: {success}/{total} files"
            if errors > 0:
                result_text += f"\nErrors: {errors}"
            if skipped > 0:
                result_text += f"\nSkipped: {skipped}"
            
            if errors == 0 and skipped == 0:
                self.progress_bar.itemconfig(self.progress_indicator, fill="#4CAF50")
                self.progress_details.config(text="✓ All files processed successfully", fg="green")
            else:
                self.progress_bar.itemconfig(self.progress_indicator, fill="#FF9800")
                self.progress_details.config(text=f"✓ {success} done, ✗ {errors} errors, ⏭️ {skipped} skipped", fg="#FF9800")
            
            messagebox.showinfo("Done", result_text)

    def stop_renaming(self):
        """Stop the renaming process"""
        self.stop_rename = True
        self.stop_btn.config(state="disabled", text="Stopping...")

    def clear(self):
        """Clear everything - files list, folder paths, progress, etc."""
        # Clear file list from treeview
        self.tree.delete(*self.tree.get_children())
        
        # Clear input folder path
        self.input_dir = None
        self.in_entry.delete(0, tk.END)
        
        # Clear output folder path
        self.output_dir = None
        self.out_entry.delete(0, tk.END)
        
        # Reset file count
        self.count_label.config(text="Total Files : 0")
        
        # Reset progress display
        self.update_progress(0, 0, 0, 0, 0, "")
        
        # Clear undo/redo history
        self.undo_stack.clear()
        self.redo_stack.clear()
        
        # Reset overwrite_all flag
        self.overwrite_all = False
        
        # Reset renaming flags
        self.is_renaming = False
        self.stop_rename = False
        
        # Enable rename button if it was disabled
        self.rename_btn.config(state="normal")
        
        # Hide stop button if visible
        if self.stop_btn.winfo_ismapped():
            self.stop_btn.pack_forget()
        
        # Update status message
        self.progress_details.config(text="All cleared and ready for new files", fg="green")
        
        # Save empty settings to file
        self.save_settings()

    def select_row_only(self, event):
        item = self.tree.identify_row(event.y)
        if item:
            self.tree.selection_set(item)

    def edit_cell(self, event):
        region = self.tree.identify("region", event.x, event.y)
        if region != "cell":
            return

        item = self.tree.identify_row(event.y)
        col = self.tree.identify_column(event.x)

        if col != "#2" or not item:
            return

        old_value = self.tree.set(item, col)
        self.undo_stack.append(("edit", item, col, old_value))
        self.redo_stack.clear()

        orig_name = self.tree.set(item, "original")
        current_new = self.tree.set(item, col)
        
        _, orig_ext = os.path.splitext(orig_name)
        
        x, y, w, h = self.tree.bbox(item, col)
        
        entry = tk.Entry(self.tree)
        entry.place(x=x, y=y, width=w, height=h)
        entry.insert(0, current_new)
        entry.select_range(0, tk.END)
        entry.focus()

        def save_and_destroy(e=None):
            new_name = entry.get()
            
            if orig_ext and not os.path.splitext(new_name)[1]:
                new_name += orig_ext
                
            self.tree.set(item, col, new_name)
            self.tree.set(item, "status", "Ready")
            self.tree.item(item, tags=('ready',))
            entry.destroy()
        
        def cancel_edit(e=None):
            entry.destroy()
        
        entry.bind("<Return>", save_and_destroy)
        entry.bind("<Escape>", cancel_edit)
        entry.bind("<FocusOut>", save_and_destroy)

    def paste_names(self, event):
        try:
            data = self.root.clipboard_get()
        except tk.TclError:
            return

        lines = [l.strip() for l in data.splitlines() if l.strip()]
        if not lines:
            return

        selected = self.tree.selection()
        if not selected:
            return "break"

        items = list(self.tree.get_children())
        start = items.index(selected[0])

        for i, name in enumerate(lines):
            if start + i >= len(items):
                break
            self.tree.set(items[start + i], "new", name)
            self.tree.set(items[start + i], "status", "Ready")
            self.tree.item(items[start + i], tags=('ready',))

        return "break"

    def validate_filename(self, name):
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            if char in name:
                return False, f"Invalid character: '{char}'"
        
        reserved_names = [
            'CON', 'PRN', 'AUX', 'NUL',
            'COM1', 'COM2', 'COM3', 'COM4', 'COM5', 'COM6', 'COM7', 'COM8', 'COM9',
            'LPT1', 'LPT2', 'LPT3', 'LPT4', 'LPT5', 'LPT6', 'LPT7', 'LPT8', 'LPT9'
        ]
        if name.upper().split('.')[0] in reserved_names:
            return False, "Reserved Windows filename"
        
        if len(name) > 255:
            return False, "Filename too long (max 255 chars)"
        
        return True, ""

    def human_readable_size(self, size):
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} TB"

    def clear_selected(self):
        selected = self.tree.selection()
        for item in selected:
            self.tree.set(item, "new", "")
            self.tree.set(item, "status", "Pending")
            self.tree.item(item, tags=('pending',))

    def undo_action(self):
        if self.undo_stack:
            action = self.undo_stack.pop()
            action_type, item, col, old_value = action
            
            if action_type == "edit":
                current_value = self.tree.set(item, col)
                self.redo_stack.append(("edit", item, col, current_value))
                self.tree.set(item, col, old_value)
                self.tree.set(item, "status", "Pending")
                self.tree.item(item, tags=('pending',))

    def redo_action(self):
        if self.redo_stack:
            action = self.redo_stack.pop()
            action_type, item, col, new_value = action
            
            if action_type == "edit":
                current_value = self.tree.set(item, col)
                self.undo_stack.append(("edit", item, col, current_value))
                self.tree.set(item, col, new_value)
                self.tree.set(item, "status", "Ready")
                self.tree.item(item, tags=('ready',))

    def save_settings(self):
        try:
            settings = {
                'input_dir': self.input_dir,
                'output_dir': self.output_dir
            }
            with open('renamer_settings.json', 'w') as f:
                json.dump(settings, f)
        except:
            pass

    def load_settings(self):
        try:
            with open('renamer_settings.json', 'r') as f:
                settings = json.load(f)
                if settings.get('input_dir') and os.path.exists(settings['input_dir']):
                    self.input_dir = settings['input_dir']
                    self.in_entry.delete(0, tk.END)
                    self.in_entry.insert(0, settings['input_dir'])
                if settings.get('output_dir') and os.path.exists(settings['output_dir']):
                    self.output_dir = settings['output_dir']
                    self.out_entry.delete(0, tk.END)
                    self.out_entry.insert(0, settings['output_dir'])
        except:
            pass

    def _bind_mousewheel(self, event):
        self.root.bind_all("<MouseWheel>", self._on_mousewheel)

    def _unbind_mousewheel(self, event):
        self.root.unbind_all("<MouseWheel>")

    def _on_mousewheel(self, event):
        self.tree.yview_scroll(int(-1 * (event.delta / 120)), "units")

if __name__ == "__main__":
    root = tk.Tk()
    app = SimpleFileRenamer(root)
    root.mainloop()