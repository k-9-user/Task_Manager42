export function isvalidemail(email)
{
	const adr = /^.+@.+\.[a-zA-Z]{2,}$/;
	return adr.test(email);
}