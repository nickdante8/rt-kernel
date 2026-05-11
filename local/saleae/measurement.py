from saleae import automation
import os
import os.path
import argparse

def main():
    # --- Argument Parsing ---
    parser = argparse.ArgumentParser(description="Automate a Saleae capture.")
    parser.add_argument('--port', type=int, default=10500, help='The automation port for the Logic 2 software.')
    parser.add_argument('--device-id', type=str, default=None, required=False, help='Device id to use for capture.')
    parser.add_argument('--duration-s', type=float, required=True, help='Capture duration in seconds.')
    parser.add_argument('--output-dir', type=str, required=True, help='Directory to save capture and exports.')
    parser.add_argument('--channels', type=int, nargs='+', required=True, help='List of digital channels to enable.')
    args = parser.parse_args()

    print(f"Connecting to Logic 2 on port {args.port}...")
    # Using the `with` statement will automatically call manager.close() when exiting the scope.
    with automation.Manager.connect(port=args.port) as manager:

        # --- Device Configuration ---
        # Configure the capturing device based on command-line arguments.
        device_configuration = automation.LogicDeviceConfiguration(
            enabled_digital_channels=args.channels,
            digital_sample_rate=8_000_000
        )

        # --- Capture Configuration ---
        # Record for the specified duration before stopping the capture.
        capture_configuration = automation.CaptureConfiguration(
            capture_mode=automation.TimedCaptureMode(duration_seconds=args.duration_s)
        )

        print(f"Starting capture for {args.duration_s} seconds on channels {args.channels}...")
        # Start a capture. The capture will be automatically closed when leaving the `with` block.
        # Note: The serial number 'A3E22C8E845D2C7D' is specific. For a general solution,
        # you can omit the `device_id` argument to use the first available real device.
        with manager.start_capture(
                device_id=args.device_id,
                device_configuration=device_configuration,
                capture_configuration=capture_configuration) as capture:

            # Wait until the capture has finished.
            capture.wait()

            # --- Data Export ---
            print(f"Capture complete. Exporting data to '{args.output_dir}'...")

            # Export analyzer data to a CSV file.
            capture.export_raw_data_csv(
                directory=args.output_dir,
                digital_channels=args.channels,
            )
            print(f"Exported measurements to {args.output_dir}")

            # Save the capture to a .sal file for later review.
            capture_filepath = os.path.join(args.output_dir, 'capture.sal')
            capture.save_capture(filepath=capture_filepath)
            print(f"Saved capture file to {capture_filepath}")

    print("Measurement script finished successfully.")

if __name__ == "__main__":
    main()
