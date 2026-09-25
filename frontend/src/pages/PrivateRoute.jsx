import { Navigate } from "react-router-dom";
import { isLoggedIn } from "../services/authService";

function PrivateRoute ({ children })
{
	if (!isLoggedIn())
		return (<Navigate to="/login" replace />);
	return (children);
}

export default PrivateRoute;
