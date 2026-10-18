/* Approved MAX Byte Map 1 layout; preserves other modes. */
(function install(settings) {
    'use strict';

    function start() {
      let attempts = 0;
      const timer = setInterval(() => {
        const map = document.getElementById('gmu-campus-map');
        const layers = document.getElementById('mb-gis-controls');
        const right = document.getElementById('mb-repaired-controls');
        const shell = document.querySelector(
          '.dashboard-container.mb-final-layout'
        );

        if (!map || !layers || !right || !shell) {
          if (++attempts >= 150) {
            clearInterval(timer);
            console.error('Approved layout: required elements did not load.');
          }
          return;
        }
        clearInterval(timer);

        // Preserve the original layout for Customize and Snack Chase.
        const originalPosition = document.createComment('GIS panel home');
        layers.before(originalPosition);

        const entries = settings.map(item => {
          const element = document.querySelector(item.selector);
          return {
            ...item, element,
            original: element?.getAttribute('style')
          };
        });

        let active = false;
        let frame;

        const set = (element, key, value) =>
          element.style.setProperty(key, value, 'important');

        function resize() {
          if (!active) return;

          const left = document.getElementById('mb-repaired-map-column');
          const modes = document.getElementById('max-byte-modes');
          const height = Math.max(
            360, innerHeight - modes.getBoundingClientRect().bottom - 36
          );

          // Desktop: equal columns, map spanning two right-hand panels.
          // Small screens: readable stacked panels with page scrolling.
          const narrow = innerWidth < 760;
          set(shell, 'width',
            Math.round(narrow
              ? innerWidth * 0.96
              : Math.min(innerWidth * 0.92, height * 1.35)) + 'px');
          set(shell, 'grid-template-columns',
            narrow ? 'minmax(0,1fr)' : 'minmax(0,1fr) minmax(0,1fr)');
          set(left, 'grid-column', '1');
          set(left, 'grid-row', '2');
          set(left, 'height', (narrow ? 460 : height) + 'px');
          set(right, 'grid-column', narrow ? '1' : '2');
          set(right, 'grid-row', narrow ? '3' : '2');
          set(right, 'height', (narrow ? 600 : height) + 'px');

          if (typeof campusMap !== 'undefined') {
            campusMap.invalidateSize({pan:false});
          }
        }

        function update() {
          cancelAnimationFrame(frame);
          frame = requestAnimationFrame(() => {
            const classic =
              document.body.classList.contains('mb-mode-1');

            if (classic && !active) {
              entries.forEach(item => {
                if (item.element) {
                  item.element.setAttribute('style', item.style);
                }
              });
              right.appendChild(layers);
              active = true;
            } else if (!classic && active) {
              entries.forEach(item => {
                if (!item.element) return;
                if (item.original === null) {
                  item.element.removeAttribute('style');
                } else {
                  item.element.setAttribute('style', item.original);
                }
              });
              originalPosition.after(layers);
              active = false;
              window.dispatchEvent(new Event('resize'));
            }

            resize();
          });
        }

        // Reapply sizing on resize and preserve other map modes.
        new MutationObserver(update).observe(document.body, {
          attributes:true, attributeFilter:['class']
        });
        window.addEventListener('resize', update);
        update();
      }, 100);
    }

    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', start, {once:true});
    } else {
      start();
    }
  })([
  {
    "selector": "body > :nth-child(1)",
    "style": "display: flex !important; flex-wrap: wrap !important; align-items: center !important; justify-content: center !important; gap: 8px 28px !important; padding: 8px 16px !important;"
  },
  {
    "selector": "body > :nth-child(1) > :nth-child(1)",
    "style": "margin: 0px !important; font-size: 24px !important;"
  },
  {
    "selector": "body > :nth-child(1) > :nth-child(2)",
    "style": "margin: 0px !important; padding: 4px !important;"
  },
  {
    "selector": "body > :nth-child(1) > :nth-child(2) > :nth-child(1)",
    "style": "margin: 0px !important; padding: 4px !important;"
  },
  {
    "selector": "body > :nth-child(2) > :nth-child(1)",
    "style": "width: 857px !important; max-width: none !important; margin: 0px auto !important; gap: 12px !important; display: grid !important; grid-template-columns: minmax(0px, 1fr) minmax(0px, 1fr) !important; grid-template-rows: auto auto !important; padding: 0px !important;"
  },
  {
    "selector": "#max-byte-modes",
    "style": "display: flex !important; flex-wrap: wrap !important; align-items: center !important; gap: 6px 14px !important; padding: 8px 12px !important; grid-area: 1 / 1 / auto / -1 !important;"
  },
  {
    "selector": "#mb-repaired-map-column",
    "style": "grid-area: 2 / 1 !important; width: 100% !important; min-width: 0px !important; padding: 10px !important; margin: 0px !important; box-sizing: border-box !important; height: 634.6px !important;"
  },
  {
    "selector": "#mb-repaired-controls",
    "style": "grid-area: 2 / 2 !important; display: grid !important; grid-template-columns: minmax(0px, 1fr) !important; grid-template-rows: minmax(0px, 1fr) minmax(0px, 1fr) !important; gap: 12px !important; width: 100% !important; min-width: 0px !important; padding: 0px !important; margin: 0px !important; height: 634.6px !important;"
  },
  {
    "selector": "#mb-repaired-map-column > :nth-child(1)",
    "style": "display: grid !important; grid-template-columns: minmax(0px, 1fr) !important; grid-template-rows: auto auto minmax(0px, 1fr) auto !important; height: 100% !important; min-height: 0px !important; gap: 6px !important; padding: 0px !important; margin: 0px !important;"
  },
  {
    "selector": "#robot-control-panel",
    "style": "background: white; color: rgb(34, 34, 34); padding: 14px !important; margin: 0px !important; border-radius: 12px; box-shadow: rgba(0, 0, 0, 0.133) 0px 2px 8px; gap: 4px 10px !important; grid-area: 1 / 1 !important; display: block !important; height: 100% !important; min-height: 0px !important; overflow: auto !important; box-sizing: border-box !important;"
  },
  {
    "selector": "#robot-simulation-status",
    "style": "margin: 0px !important; padding: 0px !important; gap: 4px 12px !important;"
  },
  {
    "selector": "#mb-gis-controls",
    "style": "background: rgb(16, 34, 56); color: rgb(255, 255, 255); padding: 14px !important; border-radius: 12px; margin: 0px !important; height: 100% !important; grid-area: 2 / 1 !important; min-height: 0px !important; max-height: none !important; width: 100% !important; overflow: auto !important; box-sizing: border-box !important;"
  },
  {
    "selector": "#gmu-campus-map",
    "style": "height: 100% !important; width: 100% !important; border-radius: 10px; min-height: 0px !important; max-height: none !important; grid-area: 3 / 1 !important; margin: 0px !important;"
  },
  {
    "selector": "#gmu-map-status",
    "style": "margin: 0px !important; padding: 0px !important; line-height: 1.3 !important; grid-area: 4 / 1 !important; font-size: 12px !important;"
  },
  {
    "selector": "#max-byte-modes > :nth-child(2) > :nth-child(1)",
    "style": "min-height: 36px !important; padding: 6px 12px !important; font-size: 14px !important;"
  },
  {
    "selector": "#max-byte-modes > :nth-child(2) > :nth-child(2)",
    "style": "min-height: 36px !important; padding: 6px 12px !important; font-size: 14px !important;"
  },
  {
    "selector": "#max-byte-modes > :nth-child(2) > :nth-child(3)",
    "style": "min-height: 36px !important; padding: 6px 12px !important; font-size: 14px !important;"
  },
  {
    "selector": "#mb-mode-desc",
    "style": "margin: 0px !important; font-size: 12px !important;"
  },
  {
    "selector": "#robot-control-panel > :nth-child(1)",
    "style": "margin: 0px !important; font-size: 13px !important; line-height: 1.4 !important;"
  },
  {
    "selector": "#robot-control-panel > :nth-child(2)",
    "style": "margin: 0px !important; font-size: 13px !important; line-height: 1.4 !important;"
  },
  {
    "selector": "#robot-start",
    "style": ""
  },
  {
    "selector": "#robot-pause",
    "style": ""
  },
  {
    "selector": "#robot-reset",
    "style": ""
  },
  {
    "selector": "#robot-control-panel > :nth-child(4)",
    "style": "margin: 0px !important; font-size: 13px !important; line-height: 1.4 !important;"
  },
  {
    "selector": "#robot-direction",
    "style": ""
  },
  {
    "selector": "#robot-simulation-status > :nth-child(1)",
    "style": "margin: 0px !important; font-size: 13px !important; line-height: 1.4 !important;"
  },
  {
    "selector": "#robot-simulation-status > :nth-child(2)",
    "style": "margin: 0px !important; font-size: 13px !important; line-height: 1.4 !important;"
  },
  {
    "selector": "#robot-simulation-status > :nth-child(3)",
    "style": "margin: 0px !important; font-size: 13px !important; line-height: 1.4 !important;"
  },
  {
    "selector": "#robot-simulation-status > :nth-child(4)",
    "style": "margin: 0px !important; font-size: 13px !important; line-height: 1.4 !important;"
  },
  {
    "selector": "#robot-simulation-status > :nth-child(5)",
    "style": "margin: 0px !important; font-size: 13px !important; line-height: 1.4 !important;"
  },
  {
    "selector": "#robot-simulation-status > :nth-child(6)",
    "style": "margin: 0px !important; font-size: 13px !important; line-height: 1.4 !important;"
  },
  {
    "selector": "#mb-repaired-map-column > :nth-child(1) > :nth-child(1)",
    "style": "margin: 0px !important; padding: 0px !important; line-height: 1.3 !important;"
  },
  {
    "selector": "#mb-repaired-map-column > :nth-child(1) > :nth-child(2)",
    "style": "margin: 0px !important; padding: 0px !important; line-height: 1.3 !important;"
  }
]);

// MAX_BYTE_CENTER_ON_RESIZE_V1
// Center the camera, never change the robot's actual coordinates.
(() => {
  let attempts = 0;
  const timer = setInterval(() => {
    const container = document.getElementById('gmu-campus-map');
    const robot = window.maxByteDeliveryRobot;

    if (
      !container || !robot ||
      typeof robot.getLatLng !== 'function' ||
      typeof campusMap === 'undefined'
    ) {
      if (++attempts >= 150) {
        clearInterval(timer);
        console.warn('Robot centering: map or marker unavailable.');
      }
      return;
    }

    clearInterval(timer);
    let frame;

    function centerRobot() {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(() => {
        // Ignore the Classic map while another mode hides it.
        if (
          !container.getClientRects().length ||
          container.clientWidth === 0 ||
          container.clientHeight === 0
        ) return;

        campusMap.invalidateSize({pan:false});
        campusMap.panTo(robot.getLatLng(), {animate:false});
      });
    }

    // Respond to the actual map dimensions, including layout changes.
    new ResizeObserver(centerRobot).observe(container);
    centerRobot();
  }, 100);
})();