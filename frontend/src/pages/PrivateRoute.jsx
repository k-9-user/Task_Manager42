import { useAuth } from "../hooks/useAuth";
import { Navigate } from "react-router-dom";

function PrivateRoute ({ children })
{
	const { isAuthen, loading } = useAuth();

	if (loading)
		return (<p>Chargement ...</p>);
	if (!!isAuthen)
		return (<Navigate to="/login"/>);
	return ({children});
}

export default PrivateRoute;