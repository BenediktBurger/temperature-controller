
from typing import Any, List, Optional, Union

from pyleco.directors.director import Director


class ControllerDirector(Director):
    """Direct a temperature controller."""

    def get_current_data(self) -> dict[str, float]:
        """Get current sensor and output data."""
        return self.ask_rpc("get_current_data")

    def get_log(self) -> list[str]:
        return self.ask_rpc("get_log")

    def reset_log(self) -> None:
        return self.ask_rpc("reset_log")

    def send_sensor_command(self, command: str) -> Any:
        return self.ask_rpc("sendSensorCommand", command=command)

    def set_output(self, name: str, value: float) -> None:
        """Set an output to a specific value."""
        return self.ask_rpc("setOutput", name=name, value=value)

    def set_PID_settings(self,
                         name: str,
                         lower_limit: Optional[float] = None,
                         upper_limit: Optional[float] = None,
                         Kp: Optional[float] = None,
                         Ki: Optional[float] = None,
                         Kd: Optional[float] = None,
                         setpoint: Optional[float] = None,
                         auto_mode: Optional[bool] = None,
                         last_output: Optional[float] = None,
                         state: Optional[int] = None,
                         sensors: Optional[List[str]] = None,
                         output_channel: Optional[str] = None,
                         ) -> None:
        self.ask_rpc(
            "set_PID_settings",
            name=name,
            lower_limit=lower_limit,
            upper_limit=upper_limit,
            Kp=Kp,
            Ki=Ki,
            Kd=Kd,
            setpoint=setpoint,
            auto_mode=auto_mode,
            last_output=last_output,
            state=state,
            sensors=sensors,
            output=output_channel,
        )

    def get_PID_settings(self, pid: Union[int, str] = 0) -> dict[str, Any]:
        return self.ask_rpc("get_PID_settings", pid=pid)

    def reset_PID(self, pid: Union[int, str] = 0) -> None:
        self.ask_rpc("reset_PID", pid=pid)

    def get_current_PID_state(self, pid: Union[int, str] = 0) -> tuple[float, float, float]:
        return self.ask_rpc("get_current_PID_state", pid=pid)

    def set_readout_interval(self, interval: float) -> None:
        self.ask_rpc("set_readout_interval", interval=interval)

    def get_readout_interval(self) -> float:
        return self.ask_rpc("get_readout_interval")

    def set_database_table(self, table_name: str) -> None:
        self.ask_rpc("set_database_table", table_name=table_name)

    def get_database_table(self) -> str:
        return self.ask_rpc("get_database_table")

    def shut_down_actor(self, actor: Union[bytes, str, None] = None) -> None:
        try:
            return super().shut_down_actor(actor)
        except TimeoutError:
            print("Timeout during shutting down actor.")
