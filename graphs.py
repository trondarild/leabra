import colorsys

import bokeh.io
from bokeh import plotting as bkp
from bokeh.core.properties import value
from bokeh.models import FixedTicker, Legend
from bokeh.models.mappers import LinearColorMapper

import ipywidgets.widgets
from ipywidgets.widgets import fixed, IntSlider, FloatSlider
# from ipywidgets.widgets import SelectionSlider # for ipywidgets 5.x


    ## Disable autoscrolling

from IPython.display import display, Javascript

disable_js = """
IPython.OutputArea.prototype._should_scroll = function(lines) {
    return false;
}
"""
display(Javascript(disable_js))


    ## Larger labels

# from IPython.display import HTML
#
# display(HTML('''<style>
#     .widget-label { min-width: 20ex !important; }
# </style>'''))


    ## Load bokeh for jupyter

bkp.output_notebook(hide_banner=True)


    ## Better default figures

def tweak_fig(fig):
    tight_layout(fig)
    disable_minor_ticks(fig)
    disable_grid(fig)
    fig.toolbar.logo = None
    fig.toolbar_location = None

def tight_layout(fig):
    fig.min_border_top    = 35
    fig.min_border_bottom = 35
    fig.min_border_right  = 35
    fig.min_border_left   = 35

def disable_minor_ticks(fig):
    #fig.axis.major_label_text_font_size = value('8pt')
    fig.axis.minor_tick_line_color = None
    fig.axis.major_tick_in = 0

def disable_grid(fig):
    fig.xgrid.grid_line_color = None
    fig.ygrid.grid_line_color = None


def figure(*args, **kwargs):
    fig = bkp.figure(*args, **kwargs)
    tweak_fig(fig)
    return fig


    ## Removing returns

def show(*args, **kwargs):
    bkp.show(*args, **kwargs)

def interact(*args, **kwargs):
    ipywidgets.widgets.interact(*args, **kwargs)

# def select(name, options):
#     return SelectionSlider(description=name,  options=list(options))

def floatslider(*args, **kwargs):
    s = FloatSlider(*args, readout_format='.3f', **kwargs)
    s.layout.width = '70%'
    return s


    ## Graphs

def line(xs, ys, std=None, fig=None, title='', width=700, height=400, dots=False, legend='None',
         color='#00a0b0', alpha=1.0, line_width=1, show=True, **kwargs):

    if fig is None:
        fig = figure(plot_width=width, plot_height=height, tools="save", title=title, **kwargs)

    fig.line(xs, ys, line_color=color, line_alpha=alpha, line_width=line_width, legend_label=legend, )
    if dots:
        fig.scatter(xs, ys, line_color=None, fill_color=color, size=4)
    if std is not None:
        assert len(std) == len(ys)
        x_std = list(xs) + list(reversed(xs))
        y_std = ([m_i + std_i for m_i, std_i in zip(ys, std)]
                 + list(reversed([m_i - std_i for m_i, std_i in zip(ys, std)])))
        fig.patch(x_std,  y_std, fill_color=color, fill_alpha=0.10, line_color=None)

    if show:
        bkp.show(fig)
    else:
        return fig

def xx1(xs, y_xx1, y_noisy_xx1, title='', width=400, height=400):
    fig = figure(plot_width=width, plot_height=height, tools="")
    fig.title.text = title
    fig.line(xs, y_xx1, legend_label='XX1',
                          line_alpha=0.5, line_width=2)
    fig.line(xs, y_noisy_xx1, legend_label='Noisy XX1',
             color='red', line_alpha=0.5, line_width=2)
    fig.legend.location = 'center_right'
    bkp.show(fig)


default_names = ('net', 'v_m', 'I_net', 'act', 'v_m_eq', 'adapt')

def _unit_activity_aux(data, names=default_names):
    """Display graph of best choice"""

    x_range = [0, len(data[names[0]])]
    fig = figure(x_range=x_range, y_range=[-0.1, 1.0],
                 plot_width=700, plot_height=450, tools="")
    fig.title.text = "Unit activity"

    colors = {'net':'black', 'v_m':'blue', 'I_net':'red', 'act':'green',
              'v_m_eq':'grey', 'adapt':'darkred',
              'avg_ss': 'cyan', 'avg_s': 'blue',
              'avg_m': 'red', 'avg_s_eff': 'orange'}

    lines = []
    for name in names:
        color = colors[name]
        line_dash = 'solid'
        if name == 'v_m_eq':
            line_dash = 'dashed'
        line = fig.line(range(len(data[name])), data[name], color=color, line_width=2,
                                                             line_dash=line_dash)
        lines.append(line)

    legend = Legend(items=[(name, [line]) for name, line in zip(names, lines)],
                    location=(10, -40))

    fig.add_layout(legend, 'right')

    return fig, [line.data_source.data for line in lines]

def unit_activity(data, names=default_names):
    """Display graph of best choice"""
    fig, lines = _unit_activity_aux(data, names=names)
    bkp.show(fig)

def unit_activity_interactive(data, names=default_names, figdata=None):
    if figdata is None:
        fig, lines = _unit_activity_aux(data)
        handle = bkp.show(fig, notebook_handle=True)
        return handle, fig, lines
    else:
        handle, fig, lines = figdata
        names = ['net', 'v_m', 'I_net', 'act']
        for name, line in zip(names, lines):
            line['y'] = data[name]
        bokeh.io.push_notebook(handle=handle)
