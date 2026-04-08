import client from "./client";

export const getForecast = (months = 3, salaryOverride = null) => {
  const params = { months };
  if (salaryOverride !== null && salaryOverride !== "") {
    params.salary_override = salaryOverride;
  }
  return client.get("/forecast", { params }).then((r) => r.data);
};
