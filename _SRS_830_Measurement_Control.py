import pyvisa
import tkinter as tk
from tkinter import ttk, messagebox
from pymeasure.instruments.srs import SR830
import threading
import time
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

# Official SR830 sensitivity map
sensitivity_map = {
    0: "2 nV", 1: "5 nV", 2: "10 nV", 3: "20 nV", 4: "50 nV",
    5: "100 nV", 6: "200 nV", 7: "500 nV", 8: "1 µV", 9: "2 µV",
    10: "5 µV", 11: "10 µV", 12: "20 µV", 13: "50 µV", 14: "100 µV",
    15: "200 µV", 16: "500 µV", 17: "1 mV", 18: "2 mV", 19: "5 mV",
    20: "10 mV", 21: "20 mV", 22: "50 mV", 23: "100 mV", 24: "200 mV",
    25: "500 mV", 26: "1 V"
}
reverse_sensitivity_map = {v: k for k, v in sensitivity_map.items()}

# Time constant map for SR830
time_constant_map = {
    0: "10 µs", 1: "30 µs", 2: "100 µs", 3: "300 µs", 4: "1 ms",
    5: "3 ms", 6: "10 ms", 7: "30 ms", 8: "100 ms", 9: "300 ms",
    10: "1 s", 11: "3 s", 12: "10 s", 13: "30 s", 14: "100 s",
    15: "300 s", 16: "1000 s", 17: "3000 s", 18: "10000 s", 19: "30000 s"
}
reverse_time_constant_map = {v: k for k, v in time_constant_map.items()}

class SR830App:
    def __init__(self, master):
        self.master = master
        self.master.title("SR830 Measurement control")

        self.id_map = {}
        self.device_widgets = {}
        self.connected_instruments = {}

        self.build_gui()
        self.scan_and_update_dropdowns()

        # Store data for plot
        self.resistances = []  # Store resistance data for plotting
        self.temperatures = []  # Store temperature data for plotting

    def build_gui(self):
        # Frame for the entire window
        main_frame = tk.Frame(self.master)
        main_frame.pack(pady=5)

        # Frame for the 3 columns
        columns_frame = tk.Frame(main_frame)
        columns_frame.pack(side=tk.TOP, padx=10)

        # Column 1 for Voltage SRS 830
        column1_frame = tk.Frame(columns_frame)
        column1_frame.pack(side=tk.LEFT, padx=10)

        # Column 2 for Current SRS 830
        column2_frame = tk.Frame(columns_frame)
        column2_frame.pack(side=tk.LEFT, padx=10)

        # Column 3 for Plot
        column3_frame = tk.Frame(columns_frame)
        column3_frame.pack(side=tk.LEFT, padx=10)

        # Refresh Button (top)
        refresh_button = tk.Button(self.master, text="🔄 Refresh Devices", command=self.scan_and_update_dropdowns)
        refresh_button.pack(pady=5)

        # Disconnect Button (top)
        disconnect_button = tk.Button(self.master, text="❌ Disconnect All", command=self.disconnect_devices)
        disconnect_button.pack(pady=5)

        # --- Voltage SRS 830 (Column 1) ---
        self.device_widgets[1] = self.create_instrument_block(column1_frame, "Voltage SRS 830")

        # --- Current SRS 830 (Column 2) ---
        self.device_widgets[2] = self.create_instrument_block(column2_frame, "Current SRS 830")

        # --- Plot (Column 3) ---
        plot_frame = tk.Frame(column3_frame)
        plot_frame.pack(pady=20)

        # Create a Matplotlib figure
        self.fig, self.ax = plt.subplots()

        # Set the background color of the plot and the figure
        self.fig.patch.set_facecolor("#2b2b2b")  # Dark background for the entire figure
        self.ax.set_facecolor("#333333")  # Dark background for the axis

        # Set axis labels and title with light text for contrast
        self.ax.set_ylabel("Resistance [Ohms]", color="white")
        self.ax.set_xlabel("Temperature [K]", color="white")
        self.ax.set_title("R vs T", color="white")

        # Enable grid with white grid lines for contrast
        self.ax.grid(True, which='both', color='white', linestyle='--', linewidth=0.5)

        # Set the color of ticks
        self.ax.tick_params(axis='x', colors='white')
        self.ax.tick_params(axis='y', colors='white')

        # Create a canvas widget for the plot
        self.canvas = FigureCanvasTkAgg(self.fig, master=plot_frame)
        self.canvas.get_tk_widget().pack()

        # Button to update plot (for simulation)
        self.update_plot_button = tk.Button(self.master, text="Update Plot", command=self.update_plot)
        self.update_plot_button.pack(pady=5)

    def create_instrument_block(self, frame, label):
        block_frame = tk.Frame(frame)
        block_frame.pack(pady=(10, 0))

        tk.Label(block_frame, text=f"Select {label}:").pack()

        var = tk.StringVar()
        dropdown = ttk.Combobox(block_frame, textvariable=var, width=60, state="readonly")
        dropdown.pack(pady=5)

        connect_button = tk.Button(block_frame, text=f"Connect {label}", command=lambda: self.connect_device(label, var))
        connect_button.pack()

        status_label = tk.Label(block_frame, text="Status: Not connected", fg="gray")
        status_label.pack()

        values_label = tk.Label(block_frame, text="Freq: ---", font=("Courier", 10))
        values_label.pack()

        # Sensitivity Dropdown
        sensitivity_label = tk.Label(block_frame, text="Select Sensitivity:")
        sensitivity_label.pack(pady=(10, 0))

        sensitivity_var = tk.StringVar()
        sensitivity_dropdown = ttk.Combobox(block_frame, textvariable=sensitivity_var, width=30, state="readonly")
        sensitivity_dropdown["values"] = list(sensitivity_map.values())
        sensitivity_dropdown.pack(pady=5)

        confirm_button = tk.Button(block_frame, text=f"Set Sensitivity {label}", command=lambda: self.set_sensitivity(label, sensitivity_var))
        confirm_button.pack(pady=5)

        # Time constant Dropdown
        time_constant_label = tk.Label(block_frame, text="Select Time Constant:")
        time_constant_label.pack(pady=(10, 0))

        time_constant_var = tk.StringVar()
        time_constant_dropdown = ttk.Combobox(block_frame, textvariable=time_constant_var, width=30, state="readonly")
        time_constant_dropdown["values"] = list(time_constant_map.values())
        time_constant_dropdown.pack(pady=5)

        confirm_tc_button = tk.Button(block_frame, text=f"Set Time Constant {label}",
                                      command=lambda: self.set_time_constant(label, time_constant_var))
        confirm_tc_button.pack(pady=5)

        return {
            "var": var,
            "dropdown": dropdown,
            "connect_button": connect_button,
            "status_label": status_label,
            "values_label": values_label,
            "sensitivity_var": sensitivity_var,
            "sensitivity_dropdown": sensitivity_dropdown,
            "time_constant_var": time_constant_var,
            "time_constant_dropdown": time_constant_dropdown,
            "instrument": None
        }

    def update_plot(self):
        # Simulating data for plot (Replace with actual data)
        resistance = 1000  # Simulate a resistance value in Ohms
        temperature = 300  # Simulate a temperature value in Kelvin

        # Append new data to the lists
        self.resistances.append(resistance)
        self.temperatures.append(temperature)

        # Update the plot with the new data
        self.ax.clear()
        self.ax.set_ylabel("Temperature [K]", color="white")
        self.ax.set_xlabel("Resistance [Ohms]", color="white")
        self.ax.set_title("R vs T", color="white")
        self.ax.plot(self.temperatures,self.resistances,  marker='o', color='b')

        # Enable grid with white grid lines for contrast
        self.ax.grid(True, which='both', color='white', linestyle='--', linewidth=0.5)

        # Redraw the plot
        self.canvas.draw()

    def scan_and_update_dropdowns(self):
        rm = pyvisa.ResourceManager()
        self.id_map.clear()

        for address in rm.list_resources():
            if "GPIB" in address:
                try:
                    inst = rm.open_resource(address)
                    idn = inst.query("*IDN?").strip()
                    self.id_map[address] = idn
                except Exception:
                    self.id_map[address] = "UNKNOWN"

        values = [f"{addr}  |  {self.id_map[addr]}" for addr in self.id_map]
        for w in self.device_widgets.values():
            w["dropdown"]["values"] = values
            w["var"].set("")

        self.connected_instruments.clear()

    def connect_device(self, label, var):
        selection = var.get()
        if not selection:
            messagebox.showerror("Error", f"Please select {label}.")
            return

        address = selection.split(" ")[0]
        idn = self.id_map.get(address, "UNKNOWN")

        selected_addrs = [w["var"].get().split(" ")[0] for w in self.device_widgets.values() if w["var"].get()]
        if selected_addrs.count(address) > 1:
            messagebox.showwarning("Duplicate Selection", f"{label} is already selected as another instrument.")
            return

        if "SR830" in idn:
            try:
                inst = SR830(address)
                self.connected_instruments[label] = inst

                w = self.device_widgets[1 if "Voltage SRS 830" in label else 2]
                w["status_label"].config(text="Status: Connected", fg="green")

                threading.Thread(target=self.update_frequency_loop, args=(label,), daemon=True).start()
            except Exception as e:
                messagebox.showerror("Connection Failed", f"{label} failed to connect.\n\nError: {e}")
        else:
            messagebox.showwarning("Wrong Instrument", f"{label} is not an SR830.\n\nIDN: {idn}")

    def update_frequency_loop(self, label):
        inst = self.connected_instruments.get(label)
        w = self.device_widgets[1 if "Voltage SRS 830" in label else 2]

        while label in self.connected_instruments:
            try:
                freq = inst.frequency
                text = f"Freq: {freq:.2f} Hz"
                w["values_label"].config(text=text)
            except Exception as e:
                w["values_label"].config(text="Read error.")
                print(f"Error reading from {label}: {e}")
                break
            time.sleep(1)

    def set_sensitivity(self, label, sensitivity_var):
        sensitivity = sensitivity_var.get()
        if not sensitivity:
            messagebox.showerror("Error", f"Please select a sensitivity for {label}.")
            return

        inst = self.connected_instruments.get(label)
        if inst:
            try:
                sens_index = reverse_sensitivity_map[sensitivity]
                inst.write(f"SENS {sens_index}")
                messagebox.showinfo("Success", f"Sensitivity for {label} set to {sensitivity}.")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to set sensitivity.\n\nError: {e}")
        else:
            messagebox.showerror("Error", f"{label} is not connected.")

    def set_time_constant(self, label, time_constant_var):
        time_const = time_constant_var.get()
        if not time_const:
            messagebox.showerror("Error", f"Please select a time constant for {label}.")
            return

        inst = self.connected_instruments.get(label)
        if inst:
            try:
                index = reverse_time_constant_map[time_const]
                inst.write(f"OFLT {index}")
                messagebox.showinfo("Success", f"Time constant for {label} set to {time_const}.")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to set time constant.\n\nError: {e}")
        else:
            messagebox.showerror("Error", f"{label} is not connected.")

    def disconnect_devices(self):
        for label, inst in self.connected_instruments.items():
            try:
                inst.write("SYST:REM")  # Switch to remote mode to disable the front panel
                print(f"Disconnected {label}.")
            except Exception as e:
                print(f"Error disconnecting {label}: {e}")

        self.connected_instruments.clear()

        for w in self.device_widgets.values():
            w["status_label"].config(text="Status: Not connected", fg="gray")
            w["values_label"].config(text="Freq: ---")

# Run the GUI
if __name__ == "__main__":
    root = tk.Tk()
    app = SR830App(root)
    root.mainloop()
