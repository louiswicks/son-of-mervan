/**
 * MSW v1-style handlers documenting the key API endpoints.
 * These are for documentation purposes and are not used directly in Jest tests
 * (which mock modules directly). They can be used with MSW in browser/Storybook.
 */
import { rest } from 'msw';

const BASE_URL = process.env.REACT_APP_API_BASE_URL || 'https://son-of-mervan-production.up.railway.app';

export const handlers = [
  // POST /login — returns JWT access token
  rest.post(`${BASE_URL}/login`, (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({ access_token: 'mock-jwt-token' }),
    );
  }),

  // POST /auth/signup — register a new user
  rest.post(`${BASE_URL}/auth/signup`, (req, res, ctx) => {
    return res(
      ctx.status(201),
      ctx.json({ message: 'Verification email sent.' }),
    );
  }),

  // POST /calculate-budget — plan monthly budget
  rest.post(`${BASE_URL}/calculate-budget`, (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        monthly_salary: 3000,
        total_expenses: 1500,
        remaining_budget: 1500,
        expenses_by_category: { Housing: 1000, Food: 500 },
      }),
    );
  }),

  // GET /monthly-tracker/:month — fetch grouped actuals for a month
  rest.get(`${BASE_URL}/monthly-tracker/:month`, (req, res, ctx) => {
    const { month: _month } = req.params; // eslint-disable-line no-unused-vars
    return res(
      ctx.status(200),
      ctx.json({
        salary_planned: 3000,
        salary_actual: 3000,
        expenses: {
          items: [],
          total: 0,
          pages: 1,
          page_size: 25,
        },
        total_actual: 0,
        remaining_actual: 3000,
      }),
    );
  }),

  // PUT /expenses/:id — update an expense
  rest.put(`${BASE_URL}/expenses/:id`, (req, res, ctx) => {
    return res(ctx.status(200), ctx.json({ success: true }));
  }),

  // DELETE /expenses/:id — delete an expense
  rest.delete(`${BASE_URL}/expenses/:id`, (req, res, ctx) => {
    return res(ctx.status(204));
  }),
];
