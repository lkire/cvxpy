"""
Copyright 2013 Steven Diamond, 2017 Akshay Agrawal, 2017 Robin Verschueren

This file is part of CVXPY.

CVXPY is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

CVXPY is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with CVXPY.  If not, see <http://www.gnu.org/licenses/>.
"""

from cvxpy import problems
from cvxpy.expressions import cvxtypes
from cvxpy.expressions.expression import Expression
from cvxpy.expressions.constants import Constant
from cvxpy.reductions import InverseData, Reduction, Solution
from cvxpy.expressions.constants import CallbackParam


class Canonicalization(Reduction):
    """TODO(akshayka): Document this class."""

    def __init__(self, canon_methods=None):
        self.canon_methods = canon_methods

    # TODO(akshayka): It appears that this class implicitly assumes that
    # the number of variables is > 0. This assumption should either be made
    # explicit or eliminated.
    def apply(self, problem):
        inverse_data = InverseData(problem)

        canon_objective, canon_constraints = self.canonicalize_tree(
            problem.objective)

        for constraint in problem.constraints:
            # canon_constr is the constraint rexpressed in terms of
            # its canonicalized arguments, and aux_constr are the constraints
            # generated while canonicalizing the arguments of the original
            # constraint
            canon_constr, aux_constr = self.canonicalize_tree(
                constraint)
            canon_constraints += aux_constr + [canon_constr]
            inverse_data.cons_id_map.update({constraint.id:
                                             canon_constr.id})

        new_problem = problems.problem.Problem(canon_objective,
                                               canon_constraints)
        return new_problem, inverse_data

    def invert(self, solution, inverse_data):
        pvars = {vid: solution.primal_vars[vid] for vid in inverse_data.id_map
                 if vid in solution.primal_vars}
        dvars = {orig_id: solution.dual_vars[vid]
                 for orig_id, vid in inverse_data.cons_id_map.items()
                 if vid in solution.dual_vars}
        return Solution(solution.status, solution.opt_val, pvars, dvars,
                        solution.attr)

    def canonicalize_tree(self, expr):
        # TODO don't copy affine expressions?
        if type(expr) == cvxtypes.partial_problem():
            canon_expr, constrs = self.canonicalize_tree(expr.args[0].objective.expr)
            for constr in expr.args[0].constraints:
                canon_constr, aux_constr = self.canonicalize_tree(constr)
                constrs += [canon_constr] + aux_constr
        else:
            canon_args = []
            constrs = []
            for arg in expr.args:
                canon_arg, c = self.canonicalize_tree(arg)
                canon_args += [canon_arg]
                constrs += c
            canon_expr, c = self.canonicalize_expr(expr, canon_args)
            constrs += c
        return canon_expr, constrs

    def canonicalize_expr(self, expr, args):
        if isinstance(expr, Expression) and not expr.variables():
            # Parameterized expressions are evaluated in a subsequent
            # reduction.
            if expr.parameters():
                rows, cols = expr.shape
                param = CallbackParam(lambda: expr.value, (rows, cols))
                return param, []
            # Non-parameterized expressions are evaluated immediately.
            else:
                return Constant(expr.value), []
        elif type(expr) in self.canon_methods:
            return self.canon_methods[type(expr)](expr, args)
        else:
            return expr.copy(args), []