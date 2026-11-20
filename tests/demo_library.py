"""Populated menus for isolated Blender regression tests only."""
from piecompose.pie_data import Item, PieMenu, MenuLibrary

MAIN = [
    Item('Frame Selected', 'view3d.view_selected'),
    Item('Rotate', 'transform.rotate', invoke=True),
    Item('Move', 'transform.translate', invoke=True),
    Item('Scale', 'transform.resize', invoke=True),
    Item('Toggle X-Ray', 'view3d.toggle_xray'),
    Item('Front View', 'view3d.view_axis'),
    Item('Modeling', 'submenu', target_menu='modeling'),
    Item('Shade Smooth', 'object.shade_smooth'),
]
MODELING = (
    Item('Shade Smooth', 'object.shade_smooth'), None,
    Item('Shade Flat', 'object.shade_flat'), None,
    Item('Back', 'back'), None, None, None,
)
EXTRAS = (
    [Item('Local View', 'view3d.localview'),
     Item('Transform Origins', 'origins'),
     Item('Cursor to Selected', 'view3d.snap_cursor_to_selected'),
     Item('Cursor to World Origin', 'view3d.snap_cursor_to_center'),
     Item('Pivot to Median', 'pivot_median'),
     Item('Pivot to Cursor', 'pivot_cursor')],
    [Item('Toggle Overlays', 'overlays'),
     Item('Frame All', 'view3d.view_all'),
     Item('Pivot to Median', 'pivot_median'),
     Item('Pivot to Cursor', 'pivot_cursor'),
     Item('Shade Smooth', 'object.shade_smooth'),
     Item('Shade Flat', 'object.shade_flat')],
)

LIBRARY = MenuLibrary({
    'main': PieMenu('Pie Menu', {'RADIAL': MAIN, 'TOP': EXTRAS[0], 'BOTTOM': EXTRAS[1]}, {'type': 'F8'}),
    'modeling': PieMenu('Modeling', {'RADIAL': list(MODELING), 'TOP': [None] * 6,
                                    'BOTTOM': [None] * 6}),
})
def install(namespace):
    namespace['publish_library'](LIBRARY)
