from utils.wireless_form2args import wireless_formfield2args

def runsig_command_builder(form_data, outfile_name):
    # Base command for running signal server
    command_base = "runsig.sh -sdf /app/DEM/one_arc_second"
    
    # Loop over the form data, adding the command line arguments
    for key, value in form_data.items():
        if key in wireless_formfield2args:
            command_base += f" {wireless_formfield2args[key]} {value}"
    
    # Static arguments can be appended at the end or configured to be included conditionally
    static_args = f"-pm 1 -res 3600 -o {outfile_name} | genkmz.sh"
    
    # Combine the base command, the dynamic arguments from form data, and static arguments
    full_command = f"{command_base} {static_args}"
    
    return full_command
    