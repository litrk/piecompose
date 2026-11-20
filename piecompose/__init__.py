"""PieCompose. SPDX-License-Identifier: GPL-3.0-or-later"""


def register():
    from . import runtime
    runtime.register()


def unregister():
    from . import runtime
    runtime.unregister()
