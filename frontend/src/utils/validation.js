export function isvalidemail(email)
{
	const adr = /^.+@.+\.[a-zA-Z]{2,}$/;
	return adr.test(email);
}

export function isvalidusername(username)
{
	const pattern = /^[A-Za-z0-9._-]{3,50}$/;
	return pattern.test(username);
}

export function isvalidpassword(password)
{
	return password.length >= 12 && password.length <= 128;
}